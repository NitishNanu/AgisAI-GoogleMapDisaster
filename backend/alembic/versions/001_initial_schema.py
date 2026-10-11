"""Initial schema — all AegisAI tables.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-08-23

Creates all production tables for the AegisAI platform in dependency order:
  1. users               — Identity and access management
  2. incidents           — Emergency incidents (PostGIS geometry)
  3. hospitals           — Medical facility registry (PostGIS)
  4. rescue_teams        — Emergency response teams (PostGIS)
  5. shelters            — Civilian evacuation shelters (PostGIS)
  6. resource_assignments — Team-to-incident dispatch records
  7. alerts              — Notification dispatch log
  8. analytics_reports    — Persisted analytics report snapshots
  9. system_metric_snapshots — Time-series KPI data points

PostGIS extension must be enabled before running this migration:
    CREATE EXTENSION IF NOT EXISTS postgis;
"""

import sqlalchemy as sa
from geoalchemy2 import Geometry

from alembic import op

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure PostGIS extension is available
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # -- 1. users --------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="CITIZEN"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("phone_number", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint(
            "role IN ('ADMIN','COMMANDER','DISPATCHER','RESPONDER','MEDICAL','ANALYST','CITIZEN')",
            name="ck_users_role",
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_id", "users", ["id"])

    # -- 2. incidents ----------------------------------------------------------
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("disaster_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(30), nullable=False, server_default="REPORTED"),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("affected_radius_meters", sa.Float(), nullable=True, server_default=sa.text("500.0")),
        sa.Column("estimated_casualties", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_commander_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_incidents_severity",
        ),
        sa.CheckConstraint(
            "status IN ('REPORTED','INVESTIGATING','RESPONDING','ACTIVE','MONITORING','RESOLVED','CANCELLED')",
            name="ck_incidents_status",
        ),
    )
    op.create_index("ix_incidents_id", "incidents", ["id"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_severity", "incidents", ["severity"])
    op.create_index("ix_incidents_disaster_type", "incidents", ["disaster_type"])
    op.create_index("ix_incidents_created_at", "incidents", ["created_at"])

    # -- 3. hospitals ----------------------------------------------------------
    op.create_table(
        "hospitals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("beds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("icu_beds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("oxygen_available", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_operational", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("phone_number", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_hospitals_id", "hospitals", ["id"])
    op.create_index("ix_hospitals_is_operational", "hospitals", ["is_operational"])

    # -- 4. rescue_teams -------------------------------------------------------
    op.create_table(
        "rescue_teams",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("team_name", sa.String(200), nullable=False),
        sa.Column("vehicle_type", sa.String(50), nullable=False),
        sa.Column("members", sa.Integer(), nullable=False, server_default=sa.text("4")),
        sa.Column("status", sa.String(30), nullable=False, server_default="AVAILABLE"),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("specialization", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('AVAILABLE','DISPATCHED','STANDBY','MAINTENANCE','OFF_DUTY')",
            name="ck_rescue_teams_status",
        ),
    )
    op.create_index("ix_rescue_teams_id", "rescue_teams", ["id"])
    op.create_index("ix_rescue_teams_status", "rescue_teams", ["status"])

    # -- 5. shelters -----------------------------------------------------------
    op.create_table(
        "shelters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("current_occupancy", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("current_occupancy >= 0", name="ck_shelters_occupancy_non_negative"),
        sa.CheckConstraint("current_occupancy <= capacity", name="ck_shelters_occupancy_le_capacity"),
    )
    op.create_index("ix_shelters_id", "shelters", ["id"])
    op.create_index("ix_shelters_is_active", "shelters", ["is_active"])

    # -- 6. resource_assignments -----------------------------------------------
    op.create_table(
        "resource_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("rescue_teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("shelter_id", sa.Integer(), sa.ForeignKey("shelters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assignment_type", sa.String(50), nullable=False, server_default="TEAM"),
        sa.Column("status", sa.String(30), nullable=False, server_default="ACTIVE"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_resource_assignments_id", "resource_assignments", ["id"])
    op.create_index("ix_resource_assignments_incident_id", "resource_assignments", ["incident_id"])
    op.create_index("ix_resource_assignments_team_id", "resource_assignments", ["team_id"])

    # -- 7. alerts -------------------------------------------------------------
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recipient_role", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_alerts_id", "alerts", ["id"])
    op.create_index("ix_alerts_is_sent", "alerts", ["is_sent"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])

    # -- 8. analytics_reports --------------------------------------------------
    op.create_table(
        "analytics_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("environment", sa.String(50), nullable=False, server_default=sa.text("'production'")),
        sa.Column("total_incidents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("active_incidents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("resolved_incidents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("critical_incidents", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_rescue_teams", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("available_rescue_teams", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("dispatched_rescue_teams", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_hospitals", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("operational_hospitals", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_hospital_beds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_icu_beds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_shelters", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("available_shelter_capacity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("average_response_time_minutes", sa.Float(), nullable=True),
        sa.Column("system_health_score", sa.Float(), nullable=True),
        sa.Column("incident_type_breakdown", sa.Text(), nullable=True),
        sa.Column("incident_severity_breakdown", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_analytics_reports_created_at", "analytics_reports", ["created_at"])
    op.create_index("ix_analytics_reports_environment", "analytics_reports", ["environment"])

    # -- 9. system_metric_snapshots --------------------------------------------
    op.create_table(
        "system_metric_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("source", sa.String(100), nullable=False, server_default=sa.text("'analytics_service'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_system_metric_snapshots_created_at", "system_metric_snapshots", ["created_at"])
    op.create_index("ix_system_metric_snapshots_metric_name", "system_metric_snapshots", ["metric_name"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("system_metric_snapshots")
    op.drop_table("analytics_reports")
    op.drop_table("alerts")
    op.drop_table("resource_assignments")
    op.drop_table("shelters")
    op.drop_table("rescue_teams")
    op.drop_table("hospitals")
    op.drop_table("incidents")
    op.drop_table("users")
