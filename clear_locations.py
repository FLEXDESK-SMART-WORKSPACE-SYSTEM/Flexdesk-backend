import argparse
import getpass
import os

from sqlalchemy import delete, select

parser = argparse.ArgumentParser(
    description="Delete all locations, floors, bays, workspaces, and their bookings."
)
parser.add_argument(
    "--confirm",
    action="store_true",
    help="Confirm permanent deletion of location and booking data.",
)
args = parser.parse_args()

if not args.confirm:
    parser.error("Pass --confirm to permanently delete location and booking data.")

password = getpass.getpass("PostgreSQL password for user postgres (hidden input): ")
if not password:
    parser.error("A PostgreSQL password is required.")
os.environ["PGPASSWORD"] = password

from app.db import SessionLocal  # noqa: E402
from app.models import Bay, Booking, Floor, Location, Workspace  # noqa: E402

with SessionLocal.begin() as db:
    location_ids = select(Location.id)
    floor_ids = select(Floor.id).where(Floor.location_id.in_(location_ids))
    bay_ids = select(Bay.id).where(Bay.floor_id.in_(floor_ids))
    workspace_ids = select(Workspace.id).where(Workspace.bay_id.in_(bay_ids))

    deleted_bookings = db.execute(
        delete(Booking).where(Booking.workspace_id.in_(workspace_ids))
    ).rowcount
    deleted_workspaces = db.execute(
        delete(Workspace).where(Workspace.bay_id.in_(bay_ids))
    ).rowcount
    deleted_bays = db.execute(delete(Bay).where(Bay.floor_id.in_(floor_ids))).rowcount
    deleted_floors = db.execute(
        delete(Floor).where(Floor.location_id.in_(location_ids))
    ).rowcount
    deleted_locations = db.execute(delete(Location)).rowcount

print(
    "Location data removed: "
    f"{deleted_locations} locations, {deleted_floors} floors, "
    f"{deleted_bays} bays, {deleted_workspaces} workspaces, "
    f"{deleted_bookings} related bookings. Users and preferences were kept."
)
