"""
AegisAI Database Base — SQLAlchemy 2.x Declarative Base.

Provides TimestampedBase, a mixin that gives every model automatic
`created_at` and `updated_at` timestamps using server-side defaults,
ensuring clock consistency regardless of application timezone.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Root SQLAlchemy 2.x declarative base.
    All ORM models must inherit from this class.
    Alembic uses `Base.metadata` for auto-generating migrations.
    """

    # Allow model instances to be compared by their primary keys
    def __repr__(self) -> str:
        """Generic repr for all ORM models."""
        cls_name = self.__class__.__name__
        pk_cols = [col.name for col in self.__table__.primary_key.columns]  # type: ignore[attr-defined]
        pk_values = {col: getattr(self, col) for col in pk_cols}
        return f"<{cls_name} {pk_values}>"

    def to_dict(self) -> dict[str, Any]:
        """Serialize model to dictionary (excludes lazy-loaded relationships)."""
        return {
            col.name: getattr(self, col.name)
            for col in self.__table__.columns  # type: ignore[attr-defined]
        }


class TimestampMixin:
    """
    Mixin providing `created_at` and `updated_at` audit timestamps.

    - `created_at`: Set by the DB server at INSERT time via `func.now()`.
    - `updated_at`: Updated by the DB server at every UPDATE via `onupdate`.

    Using server-side defaults ensures consistency even for bulk inserts
    and operations that bypass the ORM layer.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
