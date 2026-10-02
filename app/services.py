import re
from datetime import date, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .models import Booking, Location, Preference, Workspace
from .schemas import WorkspaceSearch


def available_workspaces(db: Session, criteria: WorkspaceSearch) -> list[Workspace]:
    query = select(Workspace).where(Workspace.status == "available", Workspace.capacity >= criteria.capacity)
    if criteria.workspace_type:
        query = query.where(Workspace.workspace_type == criteria.workspace_type.lower())
    if criteria.location_id:
        query = query.join(Workspace.bay)
    candidates = list(db.scalars(query).unique())
    if criteria.location_id:
        candidates = [workspace for workspace in candidates if workspace.bay.floor.location_id == criteria.location_id]
    facility_map = {"monitor": "has_monitor", "power": "has_power", "window": "has_window", "quiet": "is_quiet"}
    candidates = [workspace for workspace in candidates if all(getattr(workspace, facility_map[facility], False) for facility in criteria.required_facilities if facility in facility_map)]
    conflicts = db.scalars(select(Booking).where(Booking.booking_date == criteria.booking_date, Booking.status == "confirmed", Booking.start_time < criteria.end_time, Booking.end_time > criteria.start_time)).all()
    busy_ids = {booking.workspace_id for booking in conflicts}
    return [workspace for workspace in candidates if workspace.id not in busy_ids]


def score_workspace(workspace: Workspace, criteria: WorkspaceSearch, preference: Preference | None) -> int:
    score = 0
    if criteria.workspace_type and workspace.workspace_type == criteria.workspace_type.lower():
        score += 30
    if workspace.capacity == criteria.capacity:
        score += 10
    for facility in criteria.required_facilities:
        if getattr(workspace, {"monitor": "has_monitor", "power": "has_power", "window": "has_window", "quiet": "is_quiet"}.get(facility, ""), False):
            score += 15
    if preference:
        if preference.preferred_type == workspace.workspace_type:
            score += 20
        if preference.quiet_preference and workspace.is_quiet:
            score += 10
        facilities = (preference.preferred_facilities or "").split(",")
        score += sum(5 for facility in facilities if getattr(workspace, {"monitor": "has_monitor", "power": "has_power", "window": "has_window"}.get(facility, ""), False))
    return score


def parse_assistant_query(query: str) -> WorkspaceSearch:
    normalized = query.lower()
    requested_date = date.today() + timedelta(days=1) if "tomorrow" in normalized else date.today()
    workspace_type = next((kind for kind in ("meeting room", "focus room", "desk") if kind in normalized), None)
    facilities = [facility for facility in ("monitor", "power", "window", "quiet") if facility in normalized]
    capacity_match = re.search(r"(?:for|group|people)\s*(\d+)", normalized)
    return WorkspaceSearch(booking_date=requested_date, workspace_type=workspace_type, capacity=int(capacity_match.group(1)) if capacity_match else 1, required_facilities=facilities)
