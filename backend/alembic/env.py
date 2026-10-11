"""
AegisAI Alembic Environment — Migration Script.

Configures the Alembic migration environment to:
  - Load `Base.metadata` from all domain ORM models so autogenerate
    can detect schema changes.
  - Source the database URL from `AppSettings` rather than hardcoding
    it in alembic.ini (keeps credentials in .env only).
  - Support both offline mode (SQL script generation) and online mode
    (direct DB connection).

Usage:
    # Generate a new migration from model changes
    alembic revision --autogenerate -m "add new field"

    # Apply all pending migrations
    alembic upgrade head

    # Roll back one migration
    alembic downgrade -1
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.modules.analytics.models  # noqa: F401

# Load all models so their metadata is registered with Base before
# Alembic reads Base.metadata for autogenerate.
import app.modules.auth.models  # noqa: F401
import app.modules.hospital.models  # noqa: F401
import app.modules.incident.models  # noqa: F401
import app.modules.notification.models  # noqa: F401
import app.modules.resource.models  # noqa: F401
from alembic import context
from app.core.config.settings import settings
from app.core.database.base import Base

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Override sqlalchemy.url from AppSettings (not alembic.ini)
# This avoids hardcoding credentials in a config file.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Configure Python logging from alembic.ini if a logging section exists
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The SQLAlchemy MetaData object for `--autogenerate` support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in offline mode.

    Generates a SQL script suitable for running manually against the
    database without a live connection. Useful for production deployments
    where the migration tool cannot access the DB directly.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Include schema-level objects like sequences and check constraints
        include_schemas=True,
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in online mode.

    Establishes a live database connection and applies pending migrations
    directly. Used during local development and automated CI/CD pipelines.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        # NullPool is preferred for migration scripts — each migration
        # gets a fresh connection and there is no pool overhead.
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            # Compare server defaults to detect DEFAULT changes
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
