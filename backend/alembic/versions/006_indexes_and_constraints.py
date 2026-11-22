"""Add performance indexes and fix resource assignment status constraint.

Revision ID: 006_indexes_and_constraints
Revises: 005_audit_logs
Create Date: 2026-11-15
"""

import sqlalchemy as sa
from alembic import op

revision = "006_indexes_and_constraints"
down_revision = "005_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. ai_decisions indexes and columns
    if "ai_decisions" in tables:
        columns = [c["name"] for c in inspector.get_columns("ai_decisions")]
        if "hospital_id" not in columns:
            op.add_column(
                "ai_decisions",
                sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True),
            )

        existing_indexes = [idx["name"] for idx in inspector.get_indexes("ai_decisions")]
        if "ix_ai_decisions_incident_id" not in existing_indexes:
            op.create_index("ix_ai_decisions_incident_id", "ai_decisions", ["incident_id"], unique=False)
        if "ix_ai_decisions_resource_id" not in existing_indexes:
            op.create_index("ix_ai_decisions_resource_id", "ai_decisions", ["resource_id"], unique=False)
        if "ix_ai_decisions_hospital_id" not in existing_indexes:
            op.create_index("ix_ai_decisions_hospital_id", "ai_decisions", ["hospital_id"], unique=False)
        if "ix_ai_decisions_status_incident" not in existing_indexes:
            op.create_index("ix_ai_decisions_status_incident", "ai_decisions", ["status", "incident_id"], unique=False)

    # 2. scenarios indexes
    if "scenarios" in tables:
        scenario_indexes = [idx["name"] for idx in inspector.get_indexes("scenarios")]
        if "ix_scenarios_created_by" not in scenario_indexes:
            op.create_index("ix_scenarios_created_by", "scenarios", ["created_by"], unique=False)

    # 3. audit_logs composite index
    if "audit_logs" in tables:
        audit_indexes = [idx["name"] for idx in inspector.get_indexes("audit_logs")]
        if "ix_audit_logs_entity_type_id" not in audit_indexes and "ix_audit_logs_entity" not in audit_indexes:
            op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"], unique=False)

    # 4. resource_assignments check constraint update
    if "resource_assignments" in tables:
        dialect_name = bind.dialect.name
        if dialect_name == "postgresql":
            op.execute("ALTER TABLE resource_assignments DROP CONSTRAINT IF EXISTS ck_resource_assignments_status;")
            op.execute("""
                ALTER TABLE resource_assignments ADD CONSTRAINT ck_resource_assignments_status
                CHECK (status IN ('ASSIGNED', 'DISPATCHED', 'EN_ROUTE', 'ARRIVED', 'ON_SCENE', 'OPERATIONAL', 'MEDEVAC', 'STAGED', 'COMPLETED', 'CANCELLED', 'ACTIVE'));
            """)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "resource_assignments" in tables and bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE resource_assignments DROP CONSTRAINT IF EXISTS ck_resource_assignments_status;")

    if "audit_logs" in tables:
        op.drop_index("ix_audit_logs_entity", table_name="audit_logs")

    if "scenarios" in tables:
        op.drop_index("ix_scenarios_created_by", table_name="scenarios")

    if "ai_decisions" in tables:
        op.drop_index("ix_ai_decisions_status_incident", table_name="ai_decisions")
        op.drop_index("ix_ai_decisions_hospital_id", table_name="ai_decisions")
        op.drop_index("ix_ai_decisions_resource_id", table_name="ai_decisions")
        op.drop_index("ix_ai_decisions_incident_id", table_name="ai_decisions")
        op.drop_column("ai_decisions", "hospital_id")
