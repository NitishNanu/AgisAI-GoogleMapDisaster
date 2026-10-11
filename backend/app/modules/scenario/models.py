"""
AegisAI Scenario Module — SQLAlchemy ORM Models.
Python 3.10 compatible.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, TimestampMixin
from app.modules.scenario.enums import ScenarioRunStatus, ScenarioStatus


class Scenario(Base, TimestampMixin):
    """
    Scenario Entity — complete simulation scenario blueprint.
    Uses UUID strings for enterprise unique identification.
    """

    __tablename__ = "scenarios"

    __table_args__ = (
        Index("ix_scenarios_status", "status"),
        Index("ix_scenarios_disaster_type", "disaster_type"),
        Index("ix_scenarios_severity", "severity"),
        Index("ix_scenarios_created_by", "created_by"),
        Index("ix_scenarios_is_template", "is_template"),
        Index("ix_scenarios_lat_lon", "latitude", "longitude"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(30),
        default=ScenarioStatus.READY.value,
        nullable=False,
    )

    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Core spatial & hazard metadata for fast indexing & queries
    disaster_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius_km: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)

    population_count: Mapped[int] = mapped_column(Integer, default=50000, nullable=False)
    simulation_duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    simulation_speed: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, default=42, nullable=False)

    # Structured JSONB sub-configurations
    disaster_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    environment_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    population_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    resource_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    hospital_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    shelter_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    infrastructure_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    simulation_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    simulation_engine_version: Mapped[str] = mapped_column(String(20), default="2.0.0", nullable=False)
    scenario_schema_version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)

    # Relationships
    runs: Mapped[list["ScenarioRun"]] = relationship(
        "ScenarioRun",
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="desc(ScenarioRun.created_at)",
    )


class ScenarioRun(Base):
    """
    Scenario Run Entity — records single execution of a scenario blueprint.
    Stores initial city snapshot and result metrics for deterministic replay.
    """

    __tablename__ = "scenario_runs"

    __table_args__ = (
        Index("ix_scenario_runs_scenario_id", "scenario_id"),
        Index("ix_scenario_runs_status", "status"),
        Index("ix_scenario_runs_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    scenario_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default=ScenarioRunStatus.INITIALIZING.value,
        nullable=False,
    )

    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    simulation_engine_version: Mapped[str] = mapped_column(String(20), default="2.0.0", nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    initial_state_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    final_state_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    scenario: Mapped["Scenario"] = relationship("Scenario", back_populates="runs")
