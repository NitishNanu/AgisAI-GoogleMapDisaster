"""
AegisAI Audit Module — Domain Service.

Provides logging and retrieval utilities for audit records.
"""

from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog


class AuditService:
    @staticmethod
    def log(
        db: Session,
        action: str,
        entity_type: str,
        entity_id: str | int | None = None,
        user_id: int | None = None,
        ip_address: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Record an audit log entry in the database."""
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            ip_address=ip_address,
            details=details or {},
        )
        db.add(entry)
        try:
            db.commit()
            db.refresh(entry)
        except Exception:
            db.rollback()
            raise
        return entry

    @staticmethod
    def get_logs(
        db: Session,
        action: str | None = None,
        entity_type: str | None = None,
        user_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        """Fetch audit log records ordered by creation date descending."""
        query = db.query(AuditLog)
        if action:
            query = query.filter(AuditLog.action == action)
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        return query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit).all()
