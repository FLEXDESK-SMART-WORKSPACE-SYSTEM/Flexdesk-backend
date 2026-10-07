from datetime import date, datetime, time
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class UserRole(str, Enum):
    EMPLOYEE = "employee"
    ADMIN = "admin"


class BayType(str, Enum):
    OPEN = "open"
    QUIET = "quiet"
    MEETING = "meeting"


class WorkspaceType(str, Enum):
    DESK = "desk"
    HOT_DESK = "hot desk"
    FOCUS_ROOM = "focus room"
    MEETING_ROOM = "meeting room"
    COLLABORATION_SPACE = "collaboration space"
    PRIVATE_WORKSPACE = "private workspace"
    TRAINING_ROOM = "training room"


class WorkspaceStatus(str, Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"
    UNAVAILABLE = "unavailable"


class BookingStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class LoginEvent(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    FAILED_LOGIN = "failed_login"
    PASSWORD_RESET = "password_reset"


def enum_column(enum_class: type[Enum], name: str) -> SqlEnum:
    return SqlEnum(
        enum_class,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, default="")
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entra_subject: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    department: Mapped[str | None] = mapped_column(String(120))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        enum_column(UserRole, "flexdesk_user_role"),
        default=UserRole.EMPLOYEE,
        server_default=UserRole.EMPLOYEE.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    preferences: Mapped["Preference | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class LoginHistory(Base):
    __tablename__ = "login_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    event: Mapped[LoginEvent] = mapped_column(enum_column(LoginEvent, "flexdesk_login_event"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(120), index=True)
    address: Mapped[str | None] = mapped_column(String(255))
    floors: Mapped[list["Floor"]] = relationship(back_populates="location", cascade="all, delete-orphan")


class Floor(Base):
    __tablename__ = "floors"
    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    floor_number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[Location] = relationship(back_populates="floors")
    bays: Mapped[list["Bay"]] = relationship(back_populates="floor", cascade="all, delete-orphan")


class Bay(Base):
    __tablename__ = "bays"
    id: Mapped[int] = mapped_column(primary_key=True)
    floor_id: Mapped[int] = mapped_column(ForeignKey("floors.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    bay_type: Mapped[BayType | None] = mapped_column(enum_column(BayType, "flexdesk_bay_type"))
    floor: Mapped[Floor] = relationship(back_populates="bays")
    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="bay", cascade="all, delete-orphan")


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[int] = mapped_column(primary_key=True)
    bay_id: Mapped[int] = mapped_column(ForeignKey("bays.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    workspace_type: Mapped[WorkspaceType] = mapped_column(enum_column(WorkspaceType, "flexdesk_workspace_type"), index=True)
    capacity: Mapped[int] = mapped_column(Integer, default=1)
    has_monitor: Mapped[bool] = mapped_column(Boolean, default=False)
    has_power: Mapped[bool] = mapped_column(Boolean, default=True)
    has_window: Mapped[bool] = mapped_column(Boolean, default=False)
    is_quiet: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[WorkspaceStatus] = mapped_column(
        enum_column(WorkspaceStatus, "flexdesk_workspace_status"),
        default=WorkspaceStatus.AVAILABLE,
        server_default=WorkspaceStatus.AVAILABLE.value,
    )
    bay: Mapped[Bay] = relationship(back_populates="workspaces")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (UniqueConstraint("workspace_id", "booking_date", "start_time", "end_time", name="uq_booking_window"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    booking_date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    status: Mapped[BookingStatus] = mapped_column(
        enum_column(BookingStatus, "flexdesk_booking_status"),
        default=BookingStatus.CONFIRMED,
        server_default=BookingStatus.CONFIRMED.value,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    workspace: Mapped[Workspace] = relationship()


class Preference(Base):
    __tablename__ = "preferences"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    preferred_type: Mapped[str | None] = mapped_column(String(30))
    preferred_location: Mapped[str | None] = mapped_column(String(120))
    preferred_facilities: Mapped[str | None] = mapped_column(String(255))
    quiet_preference: Mapped[bool] = mapped_column(Boolean, default=False)
    user: Mapped[User] = relationship(back_populates="preferences")
