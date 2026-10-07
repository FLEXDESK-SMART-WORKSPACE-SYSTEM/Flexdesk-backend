import argparse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, ensure_schema, engine
from app.location_catalog import OFFICES
from app.models import Bay, Booking, Floor, Location, User, Workspace
from app.security import hash_password

Base.metadata.create_all(bind=engine)
ensure_schema()

def add_workspace_set(bay: Bay, prefix: str) -> None:
    workspace_type = (
        "focus room" if "focus" in bay.name.lower()
        else "meeting room" if "meet" in bay.name.lower() or "board room" in bay.name.lower()
        else "desk"
    )
    if any(workspace.workspace_type == workspace_type for workspace in bay.workspaces):
        return
    if workspace_type == "desk":
        bay.workspaces.extend([
            Workspace(name=f"{prefix}-01", workspace_type="desk", capacity=1, has_monitor=True, has_power=True, is_quiet=True),
            Workspace(name=f"{prefix}-02", workspace_type="desk", capacity=1, has_monitor=True, has_power=True),
            Workspace(name=f"{prefix}-03", workspace_type="desk", capacity=1, has_power=True, has_window=True),
            Workspace(name=f"{prefix}-04", workspace_type="desk", capacity=1, has_power=True),
        ])
    else:
        capacity = 2 if workspace_type == "focus room" else 8
        bay.workspaces.append(Workspace(
            name=f"{prefix}-{workspace_type.title()}",
            workspace_type=workspace_type,
            capacity=capacity,
            has_monitor=True,
            has_power=True,
            has_window=True,
            is_quiet=workspace_type == "focus room",
        ))


def seed_locations(db: Session) -> None:
    desired_locations = {office["location"]: office for office in OFFICES}
    for existing_location in db.scalars(select(Location)).all():
        desired_office = desired_locations.get(existing_location.name)
        desired_floors = {
            floor_data["name"]: floor_data for floor_data in desired_office["floors"]
        } if desired_office else {}
        stale_floors = [
            existing_floor for existing_floor in existing_location.floors
            if existing_floor.name not in desired_floors
        ]
        for stale_floor in stale_floors:
            bay_ids = [bay.id for bay in stale_floor.bays]
            if bay_ids:
                workspace_ids = select(Workspace.id).where(Workspace.bay_id.in_(bay_ids))
                db.execute(delete(Booking).where(Booking.workspace_id.in_(workspace_ids)))
            db.delete(stale_floor)
        if not desired_office:
            db.delete(existing_location)
            continue

        for existing_floor in existing_location.floors:
            floor_data = desired_floors.get(existing_floor.name)
            if not floor_data:
                continue
            wanted_bays = set(floor_data["bays"])
            for stale_bay in list(existing_floor.bays):
                if stale_bay.name not in wanted_bays:
                    workspace_ids = select(Workspace.id).where(Workspace.bay_id == stale_bay.id)
                    db.execute(delete(Booking).where(Booking.workspace_id.in_(workspace_ids)))
                    db.delete(stale_bay)

    for office in OFFICES:
        location = db.scalar(select(Location).where(Location.name == office["location"]))
        if not location:
            location = Location(name=office["location"], city=office["city"], address=office["address"])
            db.add(location)
            db.flush()
        else:
            location.city = office["city"]
            location.address = office["address"]

        for floor_data in office["floors"]:
            floor = db.scalar(select(Floor).where(Floor.location_id == location.id, Floor.name == floor_data["name"]))
            if not floor:
                floor = Floor(name=floor_data["name"], floor_number=floor_data["number"], location=location)
                db.add(floor)
                db.flush()
            else:
                floor.floor_number = floor_data["number"]

            for bay_name in floor_data["bays"]:
                bay = next((existing for existing in floor.bays if existing.name == bay_name), None)
                if not bay:
                    normalized_name = bay_name.lower()
                    bay_type = (
                        "quiet" if "focus" in normalized_name
                        else "meeting" if "meet" in normalized_name or "board room" in normalized_name
                        else "open"
                    )
                    bay = Bay(name=bay_name, bay_type=bay_type, floor=floor)
                    db.add(bay)
                prefix = f"{office['location'][:3].upper()}-{floor.name.replace(' ', '').upper()}-{bay_name[:2].upper()}"
                add_workspace_set(bay, prefix)


parser = argparse.ArgumentParser()
parser.add_argument(
    "--locations-only",
    action="store_true",
    help="Retained for compatibility; synchronizes locations and ensures the admin account exists.",
)
args = parser.parse_args()

with SessionLocal() as db:
    seed_locations(db)
    admin = db.scalar(select(User).where(User.username == "admin"))
    if not admin:
        db.add(User(
            username="admin",
            name="FLEXDESK Administrator",
            email=None,
            department="Administration",
            password_hash=hash_password("Flexdesk@123"),
            role="admin",
        ))
    db.commit()

print(f"FLEXDESK location seed complete: {len(OFFICES)} screenshot locations updated")
