"""
AegisAI Resource Module â€” ORM Models.

Defines the core entities for resource management:
- RescueTeam: Mobile response units (Fire, Medical, Hazmat, etc.)
- Shelter: Stationary refuge locations for displaced citizens
- ResourceAssignment: Dispatch records linking teams to incidents
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, TimestampMixin
from app.modules.resource.enums import AssignmentStatus, TeamStatus, VehicleType

# Build check constraint values from enum members
_VEHICLE_TYPES = "(" + ",".join(f"'{t.value}'" for t in VehicleType) + ")"
_TEAM_STATUSES = "(" + ",".join(f"'{t.value}'" for t in TeamStatus) + ")"
_ASSIGNMENT_STATUSES = "(" + ",".join(f"'{t.value}'" for t in AssignmentStatus) + ")"


class RescueTeam(Base, TimestampMixin):
    """
    Mobile emergency response unit.
    """

    __tablename__ = "rescue_teams"

    __table_args__ = (
        CheckConstraint(f"vehicle_type IN {_VEHICLE_TYPES}", name="ck_rescue_teams_vehicle"),
        CheckConstraint(f"status IN {_TEAM_STATUSES}", name="ck_rescue_teams_status"),
        CheckConstraint("members > 0", name="ck_rescue_teams_members_positive"),
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_rescue_teams_lat"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_rescue_teams_lon"),
        Index("ix_rescue_teams_status", "status"),
        Index("ix_rescue_teams_lat_lon", "latitude", "longitude"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)

    team_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    vehicle_type: Mapped[str] = mapped_column(String(50), nullable=False)

    members: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=TeamStatus.AVAILABLE.value, server_default=TeamStatus.AVAILABLE.value
    )

    latitude: Mapped[float] = mapped_column(Float, nullable=False)

    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    location = mapped_column(
        __import__("geoalchemy2", fromlist=["Geography"]).Geography(
            geometry_type="POINT",
            srid=4326,
            spatial_index=True,
        ),
        nullable=True,
    )

    # Relationships
    assignments = relationship("ResourceAssignment", back_populates="team", cascade="all, delete-orphan")


class Shelter(Base, TimestampMixin):
    """
    Stationary safe zone for citizens during an emergency.
    """

    __tablename__ = "shelters"

    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_shelters_capacity_positive"),
        CheckConstraint("current_occupancy >= 0", name="ck_shelters_occupancy_positive"),
        CheckConstraint("current_occupancy <= capacity", name="ck_shelters_occupancy_lte_capacity"),
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_shelters_lat"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_shelters_lon"),
        Index("ix_shelters_lat_lon", "latitude", "longitude"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)

    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    current_occupancy: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    latitude: Mapped[float] = mapped_column(Float, nullable=False)

    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    location = mapped_column(
        __import__("geoalchemy2", fromlist=["Geography"]).Geography(
            geometry_type="POINT",
            srid=4326,
            spatial_index=True,
        ),
        nullable=True,
    )


class ResourceAssignment(Base, TimestampMixin):
    """
    Dispatch record assigning a RescueTeam to an Incident.
    """

    __tablename__ = "resource_assignments"

    __table_args__ = (
        CheckConstraint(f"status IN {_ASSIGNMENT_STATUSES}", name="ck_resource_assignments_status"),
        Index("ix_resource_assignments_incident", "incident_id"),
        Index("ix_resource_assignments_team", "team_id"),
        Index("ix_resource_assignments_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)

    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey("rescue_teams.id", ondelete="CASCADE"), nullable=False
    )

    dispatched_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=AssignmentStatus.ASSIGNED.value, server_default=AssignmentStatus.ASSIGNED.value
    )

    estimated_arrival_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_geometry: Mapped[str | None] = mapped_column(Text, nullable=True)

    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    team = relationship("RescueTeam", back_populates="assignments", lazy="select")
    incident = relationship("Incident", foreign_keys=[incident_id], lazy="select")
    dispatcher = relationship("User", foreign_keys=[dispatched_by], lazy="select")
