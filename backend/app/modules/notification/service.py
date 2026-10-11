"""AegisAI Notification Module â€” Domain Service."""

import structlog
from sqlalchemy.orm import Session

from app.modules.notification.models import Alert
from app.modules.notification.repository import NotificationRepository
from app.modules.notification.schemas import AlertCreate

logger = structlog.get_logger("aegis_ai.notification")


class NotificationService:
    """Domain service for generating and managing system alerts."""

    @staticmethod
    def create_alert(db: Session, payload: AlertCreate) -> Alert:
        """Create a new alert (can be triggered internally or via API)."""
        repo = NotificationRepository(db)
        alert = repo.create(**payload.model_dump())

        logger.info(
            "alert_created",
            alert_id=alert.id,
            severity=alert.severity,
            target_role=alert.target_role,
            target_user=alert.target_user_id
        )
        return alert

    @staticmethod
    def get_my_alerts(db: Session, user_id: int, user_role: str, page: int = 1, page_size: int = 50, unread_only: bool = False) -> tuple[list[Alert], int]:
        """Fetch alerts specifically for the given user."""
        repo = NotificationRepository(db)
        skip = (page - 1) * page_size
        return repo.get_user_alerts(user_id, user_role, skip, limit=page_size, unread_only=unread_only)

    @staticmethod
    def mark_alerts_read(db: Session, alert_ids: list[int], user_id: int, user_role: str) -> int:
        """Mark alerts as read for the user."""
        repo = NotificationRepository(db)
        count = repo.mark_as_read(alert_ids, user_id, user_role)
        if count > 0:
            logger.info("alerts_marked_read", user_id=user_id, count=count)
        return count
