import os
import hashlib
import logging
import secrets
from datetime import date, time

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from authlib.integrations.starlette_client import OAuth
from fastapi.responses import RedirectResponse
from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from starlette.middleware.sessions import SessionMiddleware

from .db import Base, engine, ensure_schema, get_db
from .location_catalog import LOCATION_NAMES, OFFICES
from .models import Bay, Booking, Floor, Location, Preference, User, Workspace
from .schemas import AssistantRequest, BookingCreate, BookingOut, FloorOut, LocationOut, LoginRequest, LoginResponse, PreferenceIn, PreferenceOut, RecommendationRequest, UserOut, WorkspaceOut, WorkspaceSearch
from .services import available_workspaces, parse_assistant_query, score_workspace

Base.metadata.create_all(bind=engine)
ensure_schema()
app = FastAPI(title="FLEXDESK Backend", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://localhost:5174"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
logger = logging.getLogger(__name__)
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5174").rstrip("/")
tenant_id = os.getenv("MICROSOFT_TENANT_ID", "").strip()
session_secret = os.getenv("SSO_SESSION_SECRET", "")
oauth = OAuth()
LOCATION_CATALOG = {office["location"]: office for office in OFFICES}

if tenant_id and os.getenv("MICROSOFT_CLIENT_ID") and os.getenv("MICROSOFT_CLIENT_SECRET"):
    oauth.register(
        name="microsoft",
        client_id=os.environ["MICROSOFT_CLIENT_ID"],
        client_secret=os.environ["MICROSOFT_CLIENT_SECRET"],
        server_metadata_url=f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile email"},
    )

if session_secret:
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        same_site="lax",
        https_only=os.getenv("SSO_COOKIE_SECURE", "false").lower() == "true",
    )


def demo_auth_enabled() -> bool:
    return os.getenv("ALLOW_DEMO_AUTH", "false").lower() == "true"


def access_token(user: User) -> str:
    secret = os.getenv("AUTH_TOKEN_SECRET")
    if not secret:
        if demo_auth_enabled():
            return str(user.id)
        raise HTTPException(status_code=503, detail="AUTH_TOKEN_SECRET is not configured")
    return URLSafeTimedSerializer(secret, salt="flexdesk-access").dumps({"sub": user.id})


def sso_redirect(fragment: str) -> RedirectResponse:
    return RedirectResponse(f"{frontend_url}/#{fragment}", status_code=303)


def sso_configured() -> bool:
    return bool(
        tenant_id
        and os.getenv("MICROSOFT_CLIENT_ID")
        and os.getenv("MICROSOFT_CLIENT_SECRET")
        and os.getenv("MICROSOFT_REDIRECT_URI")
        and session_secret
        and os.getenv("AUTH_TOKEN_SECRET")
        and oauth.create_client("microsoft")
    )


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if token.isdigit() and demo_auth_enabled():
        user = db.get(User, int(token))
    else:
        user = None
        secret = os.getenv("AUTH_TOKEN_SECRET")
        if secret:
            try:
                claims = URLSafeTimedSerializer(secret, salt="flexdesk-access").loads(token, max_age=43200)
                user = db.get(User, int(claims["sub"]))
            except (BadData, KeyError, TypeError, ValueError):
                user = None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="A valid bearer token is required")
    return user


def password_digest(password: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), b"flexdesk-auth", 120_000).hex()


@app.post("/api/v1/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    if user and user.password_hash and user.password_hash == password_digest(payload.password):
        return {"access_token": access_token(user), "user": user}
    if os.getenv("ALLOW_DEMO_AUTH", "false").lower() == "true":
        if not user:
            name = email.partition("@")[0].replace(".", " ").replace("_", " ").replace("-", " ").strip().title()[:120] or "Demo User"
            user = User(
                username=f"demo_{secrets.token_hex(8)}",
                name=name,
                email=email,
                department="Demo",
                password_hash=password_digest(payload.password),
            )
            db.add(user)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                user = db.scalar(select(User).where(User.email == email))
                if not user:
                    raise
            else:
                db.refresh(user)
        return {"access_token": access_token(user), "user": user}
    raise HTTPException(status_code=401, detail="Invalid email or password")


@app.get("/api/v1/auth/me", response_model=UserOut)
def auth_me(user: User = Depends(current_user)):
    return user


@app.get("/api/v1/auth/sso")
async def microsoft_sso(request: Request):
    if not sso_configured():
        return sso_redirect("sso_error=not_configured")
    return await oauth.microsoft.authorize_redirect(request, os.environ["MICROSOFT_REDIRECT_URI"])


@app.get("/api/v1/auth/sso/callback", name="microsoft_sso_callback")
async def microsoft_sso_callback(request: Request, db: Session = Depends(get_db)):
    if not sso_configured():
        return sso_redirect("sso_error=not_configured")
    try:
        token = await oauth.microsoft.authorize_access_token(request)
        claims = token.get("userinfo") or {}
        claimed_tenant = str(claims.get("tid", "")).lower()
        subject = str(claims.get("oid") or claims.get("sub") or "")
        email = str(claims.get("email") or claims.get("preferred_username") or claims.get("upn") or "").strip().lower()
        if claimed_tenant != tenant_id.lower() or not subject or "@" not in email or len(email) > 255:
            return sso_redirect("sso_error=identity_not_allowed")

        entra_subject = f"{claimed_tenant}:{subject}"
        user = db.scalar(select(User).where(User.entra_subject == entra_subject))
        if not user:
            user = db.scalar(select(User).where(func.lower(User.email) == email))
            if user and user.entra_subject and user.entra_subject != entra_subject:
                return sso_redirect("sso_error=account_conflict")
            if not user:
                identity_key = hashlib.sha256(entra_subject.encode()).hexdigest()
                user = User(
                    username=f"entra_{identity_key}",
                    name=str(claims.get("name") or email.partition("@")[0])[:120],
                    email=email,
                    department=claims.get("department"),
                    entra_subject=entra_subject,
                )
                db.add(user)
            else:
                user.entra_subject = entra_subject
        if claims.get("name"):
            user.name = str(claims["name"])[:120]
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            user = db.scalar(select(User).where(User.entra_subject == entra_subject))
            if not user:
                raise
        else:
            db.refresh(user)
        return sso_redirect(f"access_token={access_token(user)}")
    except Exception:
        db.rollback()
        logger.exception("Microsoft Entra sign-in failed")
        return sso_redirect("sso_error=authentication_failed")


@app.get("/health")
def health():
    return {"status": "ok", "service": "flexdesk-backend"}


def location_catalog_ready(db: Session) -> bool:
    locations = db.scalars(
        select(Location)
        .options(selectinload(Location.floors).selectinload(Floor.bays))
        .where(Location.name.in_(LOCATION_NAMES))
    ).all()
    if len(locations) != len(LOCATION_NAMES):
        return False
    if {location.name for location in locations} != set(LOCATION_NAMES):
        return False

    for location in locations:
        expected_floors = LOCATION_CATALOG[location.name]["floors"]
        floors = {floor.name: floor for floor in location.floors}
        if len(floors) != len(location.floors) or set(floors) != {
            floor["name"] for floor in expected_floors
        }:
            return False
        for floor_spec in expected_floors:
            bays = floors[floor_spec["name"]].bays
            if len(bays) != len(floor_spec["bays"]) or {
                bay.name for bay in bays
            } != set(floor_spec["bays"]):
                return False
    return True


def ordered_locations(db: Session) -> list[Location]:
    rows = db.scalars(
        select(Location).where(Location.name.in_(LOCATION_NAMES))
    ).all()
    order = {name: index for index, name in enumerate(LOCATION_NAMES)}
    return sorted(rows, key=lambda location: order[location.name])


@app.get("/api/v1/locations", response_model=list[LocationOut])
def locations(db: Session = Depends(get_db)):
    if not location_catalog_ready(db):
        return []
    return ordered_locations(db)


@app.get("/api/v1/locations/hierarchy")
def location_hierarchy(db: Session = Depends(get_db)):
    if not location_catalog_ready(db):
        return []
    locations = db.scalars(
        select(Location)
        .options(
            selectinload(Location.floors)
            .selectinload(Floor.bays)
            .selectinload(Bay.workspaces)
        )
        .where(Location.name.in_(LOCATION_NAMES))
    ).all()
    locations.sort(key=lambda location: LOCATION_NAMES.index(location.name))

    hierarchy = []
    for location in locations:
        office = LOCATION_CATALOG[location.name]
        floor_order = {floor["name"]: index for index, floor in enumerate(office["floors"])}
        floors_data = []
        for floor in sorted(location.floors, key=lambda item: floor_order[item.name]):
            floor_spec = office["floors"][floor_order[floor.name]]
            bay_order = {name: index for index, name in enumerate(floor_spec["bays"])}
            bays_data = [{
                "id": bay.id,
                "name": bay.name,
                "type": bay.bay_type,
                "workspaces": [{
                    "id": workspace.id,
                    "name": workspace.name,
                    "type": workspace.workspace_type,
                    "capacity": workspace.capacity,
                    "status": workspace.status,
                } for workspace in sorted(bay.workspaces, key=lambda item: item.id)],
            } for bay in sorted(floor.bays, key=lambda item: bay_order[item.name])]
            floors_data.append({
                "id": floor.id,
                "number": floor.floor_number,
                "name": floor.name,
                "bays": bays_data,
            })
        hierarchy.append({
            "id": location.id,
            "name": location.name,
            "city": location.city,
            "address": location.address,
            "floors": floors_data,
        })
    return hierarchy


@app.get("/api/v1/floors", response_model=list[FloorOut])
def floors(location_id: int | None = None, db: Session = Depends(get_db)):
    if not location_catalog_ready(db):
        return []
    query = select(Floor).order_by(Floor.id)
    if location_id:
        query = query.where(
            Floor.location_id == location_id,
            Floor.location_id.in_(
                select(Location.id).where(Location.name.in_(LOCATION_NAMES))
            ),
        )
    else:
        query = query.where(
            Floor.location_id.in_(
                select(Location.id).where(Location.name.in_(LOCATION_NAMES))
            )
        )
    return db.scalars(query).all()


@app.get("/api/v1/workspaces", response_model=list[WorkspaceOut])
def workspaces(db: Session = Depends(get_db)):
    if not location_catalog_ready(db):
        return []
    return db.scalars(
        select(Workspace)
        .where(
            Workspace.bay_id.in_(
                select(Bay.id)
                .join(Floor, Bay.floor_id == Floor.id)
                .join(Location, Floor.location_id == Location.id)
                .where(Location.name.in_(LOCATION_NAMES))
            )
        )
        .order_by(Workspace.id)
    ).all()


@app.get("/api/v1/workspaces/available", response_model=list[WorkspaceOut])
def available(
    booking_date: date,
    start_time: time = time(9, 0),
    end_time: time = time(17, 0),
    location_id: int | None = None,
    workspace_type: str | None = None,
    capacity: int = 1,
    required_facilities: list[str] = Query(default=[]),
    db: Session = Depends(get_db),
):
    criteria = WorkspaceSearch(booking_date=booking_date, start_time=start_time, end_time=end_time, location_id=location_id, workspace_type=workspace_type, capacity=capacity, required_facilities=required_facilities)
    return available_workspaces(db, criteria)


@app.post("/api/v1/bookings", response_model=BookingOut, status_code=201)
def create_booking(payload: BookingCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    criteria = WorkspaceSearch(booking_date=payload.booking_date, start_time=payload.start_time, end_time=payload.end_time)
    if payload.end_time <= payload.start_time:
        raise HTTPException(400, "end_time must be later than start_time")
    if payload.workspace_id not in {workspace.id for workspace in available_workspaces(db, criteria)}:
        raise HTTPException(409, "Workspace is unavailable for the requested time")
    booking = Booking(user_id=user.id, **payload.model_dump())
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


@app.get("/api/v1/bookings", response_model=list[BookingOut])
def bookings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Booking).where(Booking.user_id == user.id).order_by(Booking.booking_date.desc())).all()


@app.delete("/api/v1/bookings/{booking_id}")
def cancel_booking(booking_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    booking = db.scalar(select(Booking).where(Booking.id == booking_id, Booking.user_id == user.id))
    if not booking:
        raise HTTPException(404, "Booking not found")
    booking.status = "cancelled"
    db.commit()
    return {"id": booking.id, "status": booking.status}


@app.get("/api/v1/preferences", response_model=PreferenceOut)
def get_preferences(user: User = Depends(current_user), db: Session = Depends(get_db)):
    preference = db.scalar(select(Preference).where(Preference.user_id == user.id))
    if not preference:
        preference = Preference(user_id=user.id, preferred_facilities="")
        db.add(preference)
        db.commit()
        db.refresh(preference)
    return preference


@app.put("/api/v1/preferences", response_model=PreferenceOut)
def update_preferences(payload: PreferenceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    preference = db.scalar(select(Preference).where(Preference.user_id == user.id)) or Preference(user_id=user.id)
    for key, value in payload.model_dump().items():
        setattr(preference, "preferred_facilities" if key == "preferred_facilities" else key, ",".join(value) if key == "preferred_facilities" else value)
    db.add(preference)
    db.commit()
    db.refresh(preference)
    return preference


@app.post("/api/v1/recommendations")
def recommendations(payload: RecommendationRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    preference = db.scalar(select(Preference).where(Preference.user_id == user.id))
    candidates = available_workspaces(db, payload)
    return [{"workspace": WorkspaceOut.model_validate(workspace), "score": score_workspace(workspace, payload, preference)} for workspace in sorted(candidates, key=lambda item: score_workspace(item, payload, preference), reverse=True)[:payload.limit]]


@app.get("/api/v1/predictions/demand")
def demand_prediction(db: Session = Depends(get_db)):
    rows = db.execute(select(Workspace.workspace_type, func.count(Booking.id)).join(Booking, Booking.workspace_id == Workspace.id, isouter=True).where(Booking.status == "confirmed").group_by(Workspace.workspace_type)).all()
    return [{"workspace_type": workspace_type, "historical_bookings": count, "predicted_demand": round(count * 1.1, 2)} for workspace_type, count in rows]


@app.post("/api/v1/assistant/query")
def assistant(payload: AssistantRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    criteria = parse_assistant_query(payload.query)
    preference = db.scalar(select(Preference).where(Preference.user_id == user.id))
    options = available_workspaces(db, criteria)
    ranked = sorted(options, key=lambda item: score_workspace(item, criteria, preference), reverse=True)[:10]
    return {"criteria": criteria.model_dump(), "recommendations": [{"workspace": WorkspaceOut.model_validate(item), "score": score_workspace(item, criteria, preference)} for item in ranked]}


@app.get("/api/v1/analytics/utilisation")
def utilisation(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(Workspace.id))) or 0
    booked = db.scalar(select(func.count(func.distinct(Booking.workspace_id))).where(Booking.status == "confirmed")) or 0
    return {"workspace_count": total, "booked_workspace_count": booked, "utilisation_percent": round(booked / total * 100, 2) if total else 0, "booking_count": db.scalar(select(func.count(Booking.id)).where(Booking.status == "confirmed")) or 0}
