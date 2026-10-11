"""
AegisAI Database Session Compatibility Shim.

Forwards to canonical session factory at `app.core.database.session`.
"""

from app.core.database.session import Base, SessionLocal, create_all_tables, engine, get_db

__all__ = ["Base", "SessionLocal", "create_all_tables", "engine", "get_db"]
