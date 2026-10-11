"""
AegisAI Database Declarative Base Compatibility Shim.

Forwards to canonical Base at `app.core.database.base`.
"""

from app.core.database.base import Base, TimestampMixin

__all__ = ["Base", "TimestampMixin"]
