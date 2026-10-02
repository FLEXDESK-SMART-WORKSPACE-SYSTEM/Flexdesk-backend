import os
import hashlib
from datetime import date, time

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import Base, engine, ensure_schema, get_db
from .models import Bay, Booking, Floor, Location, Preference, User, Workspace
from .schemas import AssistantRequest, BookingCreate, BookingOut, FloorOut, LocationOut, LoginRequest, LoginResponse, PreferenceIn, PreferenceOut, RecommendationRequest, WorkspaceOut, WorkspaceSearch
from .services import available_workspaces, parse_assistant_query, score_workspace

Base.metadata.create_all(bind=engine)
ensure_schema()
app = FastAPI(title="FLEXDESK Backend", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://localhost:5174"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    token = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if token.isdigit():
        user = db.get(User, int(token))
    elif os.getenv("ALLOW_DEMO_AUTH", "true").lower() == "true":
        user = db.scalar(select(User).order_by(User.id))
    else:
        user = None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="A valid bearer token is required")
    return user


def password_digest(password: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), b"flexdesk-auth", 120_000).hex()


@app.post("/api/v1/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username.lower().strip()))
    if not user or not user.password_hash or user.password_hash != password_digest(payload.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"access_token": str(user.id), "user": user}


@app.get("/health")
def health():
    return {"status": "ok", "service": "flexdesk-backend"}


@app.get("/api/v1/locations", response_model=list[LocationOut])
def locations(db: Session = Depends(get_db)):
    return db.scalars(select(Location).order_by(Location.name)).all()


@app.get("/api/v1/locations/hierarchy")
def location_hierarchy(db: Session = Depends(get_db)):
    locations = [location for location in db.scalars(select(Location).order_by(Location.name)).all() if location.name != "Hyderabad Office"]
    return [{
        "id": location.id,
        "name": location.name,
        "city": location.city,
        "address": location.address,
        "floors": [{
            "id": floor.id,
            "number": floor.floor_number,
            "name": floor.name,
            "bays": [{
                "id": bay.id,
                "name": bay.name,
                "type": bay.bay_type,
                "workspaces": [{
                    "id": workspace.id,
                    "name": workspace.name,
                    "type": workspace.workspace_type,
                    "capacity": workspace.capacity,
                    "status": workspace.status,
                } for workspace in bay.workspaces],
            } for bay in floor.bays],
        } for floor in location.floors],
    } for location in locations]


@app.get("/api/v1/floors", response_model=list[FloorOut])
def floors(location_id: int | None = None, db: Session = Depends(get_db)):
    query = select(Floor).order_by(Floor.floor_number)
    if location_id:
        query = query.where(Floor.location_id == location_id)
    return db.scalars(query).all()


@app.get("/api/v1/workspaces", response_model=list[WorkspaceOut])
def workspaces(db: Session = Depends(get_db)):
    return db.scalars(select(Workspace).order_by(Workspace.id)).all()


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
