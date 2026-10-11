"""Phase 2 schema fixes — align ORM models with forecaster and AI engine.

Revision ID: 004_schema_fixes
Revises: 003_prediction_intelligence
Create Date: 2026-09-08

Changes in this migration:
  1. hospitals  — rename beds→total_beds, icu_beds→icu_capacity,
                  add available_beds, available_icu, add CHECK constraints
  2. incidents  — add estimated_casualties, critical_patients, priority columns
  3. hospitals  — add explicit GIST spatial index (belt-and-suspenders)
  4. incidents  — add explicit GIST spatial index

These changes fix the 3-way schema drift between ORM, migration 001, and the
TimeHorizonForecaster / StateAggregator that caused forecasts to use fabricated
default constants instead of live DB values.
"""

import sqlalchemy as sa

from alembic import op

revision = "004_schema_fixes"
down_revision = "003_prediction_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # 1. hospitals table — capacity column rename + availability tracking #
    # ------------------------------------------------------------------ #

    # Rename existing columns to canonical names
    op.alter_column("hospitals", "beds", new_column_name="total_beds")
    op.alter_column("hospitals", "icu_beds", new_column_name="icu_capacity")

    # Add availability tracking columns (default to total so existing rows
    # start at 100% availability; operators update during incidents)
    op.add_column(
        "hospitals",
        sa.Column(
            "available_beds",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Currently unoccupied beds — decremented on patient admission",
        ),
    )
    op.add_column(
        "hospitals",
        sa.Column(
            "available_icu",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Currently unoccupied ICU beds",
        ),
    )

    # Seed available_beds = total_beds and available_icu = icu_capacity for
    # existing rows so forecasts don't see 0-availability on first deploy.
    op.execute(
        "UPDATE hospitals SET available_beds = total_beds, available_icu = icu_capacity"
    )

    # Drop the old CHECK constraints that referenced the old column names
    op.execute("ALTER TABLE hospitals DROP CONSTRAINT IF EXISTS ck_hospitals_beds_positive")
    op.execute("ALTER TABLE hospitals DROP CONSTRAINT IF EXISTS ck_hospitals_icu_positive")
    op.execute("ALTER TABLE hospitals DROP CONSTRAINT IF EXISTS ck_hospitals_icu_lte_beds")

    # Add updated CHECK constraints with canonical column names
    op.create_check_constraint(
        "ck_hospitals_beds_positive", "hospitals", "total_beds >= 0"
    )
    op.create_check_constraint(
        "ck_hospitals_icu_positive", "hospitals", "icu_capacity >= 0"
    )
    op.create_check_constraint(
        "ck_hospitals_icu_lte_beds", "hospitals", "icu_capacity <= total_beds"
    )
    op.create_check_constraint(
        "ck_hospitals_avail_beds_nn", "hospitals", "available_beds >= 0"
    )
    op.create_check_constraint(
        "ck_hospitals_avail_icu_nn", "hospitals", "available_icu >= 0"
    )
    op.create_check_constraint(
        "ck_hospitals_avail_lte_total", "hospitals", "available_beds <= total_beds"
    )
    op.create_check_constraint(
        "ck_hospitals_avail_icu_lte_cap", "hospitals", "available_icu <= icu_capacity"
    )

    # ------------------------------------------------------------------ #
    # 2. incidents table — add missing casualty + priority columns         #
    # ------------------------------------------------------------------ #

    op.add_column(
        "incidents",
        sa.Column(
            "estimated_casualties",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Total casualties (dead + seriously injured)",
        ),
    )
    op.add_column(
        "incidents",
        sa.Column(
            "critical_patients",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Patients requiring immediate ICU-level care",
        ),
    )
    op.add_column(
        "incidents",
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default="MEDIUM",
            comment="Dispatch priority: LOW|MEDIUM|HIGH|CRITICAL",
        ),
    )

    # Index priority for AI engine queries
    op.create_index("ix_incidents_priority", "incidents", ["priority"])

    # ------------------------------------------------------------------ #
    # 3. Explicit GIST spatial indexes (belt-and-suspenders — some PG     #
    #    versions don't auto-create them from GeoAlchemy2 Geography)      #
    # ------------------------------------------------------------------ #
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_hospitals_location_gist "
        "ON hospitals USING GIST (location)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_incidents_location_gist "
        "ON incidents USING GIST (location)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_rescue_teams_location_gist "
        "ON rescue_teams USING GIST (location)"
    )


def downgrade() -> None:
    # Remove GIST indexes
    op.execute("DROP INDEX IF EXISTS ix_hospitals_location_gist")
    op.execute("DROP INDEX IF EXISTS ix_incidents_location_gist")
    op.execute("DROP INDEX IF EXISTS ix_rescue_teams_location_gist")

    # Remove incident columns
    op.drop_index("ix_incidents_priority", table_name="incidents")
    op.drop_column("incidents", "priority")
    op.drop_column("incidents", "critical_patients")
    op.drop_column("incidents", "estimated_casualties")

    # Remove hospital availability columns and constraints
    op.execute("ALTER TABLE hospitals DROP CONSTRAINT IF EXISTS ck_hospitals_avail_icu_lte_cap")
    op.execute("ALTER TABLE hospitals DROP CONSTRAINT IF EXISTS ck_hospitals_avail_lte_total")
    op.execute("ALTER TABLE hospitals DROP CONSTRAINT IF EXISTS ck_hospitals_avail_icu_nn")
    op.execute("ALTER TABLE hospitals DROP CONSTRAINT IF EXISTS ck_hospitals_avail_beds_nn")
    op.execute("ALTER TABLE hospitals DROP CONSTRAINT IF EXISTS ck_hospitals_icu_lte_beds")
    op.execute("ALTER TABLE hospitals DROP CONSTRAINT IF EXISTS ck_hospitals_icu_positive")
    op.execute("ALTER TABLE hospitals DROP CONSTRAINT IF EXISTS ck_hospitals_beds_positive")

    op.drop_column("hospitals", "available_icu")
    op.drop_column("hospitals", "available_beds")

    op.alter_column("hospitals", "icu_capacity", new_column_name="icu_beds")
    op.alter_column("hospitals", "total_beds", new_column_name="beds")

    op.create_check_constraint("ck_hospitals_beds_positive", "hospitals", "beds >= 0")
    op.create_check_constraint("ck_hospitals_icu_positive", "hospitals", "icu_beds >= 0")
    op.create_check_constraint(
        "ck_hospitals_icu_lte_beds", "hospitals", "icu_beds <= beds"
    )
