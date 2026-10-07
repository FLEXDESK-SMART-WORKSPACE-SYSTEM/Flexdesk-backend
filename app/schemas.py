from datetime import date, datetime, time

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_password_strength(password: str) -> str:
    if not re.fullmatch(r"(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,256}", password):
        raise ValueError("Password must be at least 8 characters and include uppercase, lowercase, number and special character.")
    return password


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(ORMModel):
    id: int
    username: str
    name: str
    email: str | None = None
    department: str | None = None
    role: str = "employee"


class LoginRequest(BaseModel):
    employee_id: str = Field(pattern=r"^(?:[0-9]{5}|admin)$")
    password: str = Field(max_length=256)


class PasswordCreateRequest(BaseModel):
    employee_id: str = Field(pattern=r"^[0-9]{5}$")
    password: str = Field(min_length=8, max_length=256)

    _validate_password = field_validator("password")(validate_password_strength)


class PasswordResetRequest(BaseModel):
    employee_id: str = Field(pattern=r"^[0-9]{5}$")
    password: str | None = Field(default=None, min_length=8, max_length=256)

    _validate_password = field_validator("password")(validate_password_strength)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LocationOut(ORMModel):
    id: int
    name: str
    city: str
    address: str | None = None


class FloorOut(ORMModel):
    id: int
    location_id: int
    floor_number: int
    name: str


class WorkspaceOut(ORMModel):
    id: int
    bay_id: int
    name: str
    workspace_type: str
    capacity: int
    has_monitor: bool
    has_power: bool
    has_window: bool
    is_quiet: bool
    status: str


class BookingCreate(BaseModel):
    workspace_id: int
    booking_date: date
    start_time: time
    end_time: time


class BookingOut(ORMModel):
    id: int
    user_id: int
    workspace_id: int
    booking_date: date
    start_time: time
    end_time: time
    status: str
    created_at: datetime


class PreferenceIn(BaseModel):
    preferred_type: str | None = None
    preferred_location: str | None = None
    preferred_facilities: list[str] = Field(default_factory=list)
    quiet_preference: bool = False


class PreferenceOut(ORMModel):
    id: int
    user_id: int
    preferred_type: str | None
    preferred_location: str | None
    preferred_facilities: str | None
    quiet_preference: bool


class WorkspaceSearch(BaseModel):
    booking_date: date
    start_time: time = time(9, 0)
    end_time: time = time(17, 0)
    location_id: int | None = None
    workspace_type: str | None = None
    capacity: int = Field(default=1, ge=1)
    required_facilities: list[str] = Field(default_factory=list)


class RecommendationRequest(WorkspaceSearch):
    limit: int = Field(default=10, ge=1, le=50)


class AssistantRequest(BaseModel):
    query: str = Field(min_length=3)
