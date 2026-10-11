"""AegisAI Notification Module â€” Repository Layer."""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.modules.notification.models import Alert


class NotificationRepository:
    """Data access layer for system alerts."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, **kwargs: object) -> Alert:
        alert = Alert(**kwargs)
        self._db.add(alert)
        self._db.commit()
        self._db.refresh(alert)
        return alert

    def get_user_alerts(self, user_id: int, user_role: str, skip: int = 0, limit: int = 50, unread_only: bool = False) -> tuple[list[Alert], int]:
        """
        Fetch alerts that are targeted to a specific user ID OR their role,
        OR broadcast alerts (where both are None).
        """
        query = self._db.query(Alert).filter(
            or_(
                Alert.target_user_id == user_id,
                Alert.target_role == user_role,
                (Alert.target_user_id.is_(None) & Alert.target_role.is_(None))
            )
        )

        if unread_only:
            query = query.filter(Alert.is_read.is_(False))

        total = query.count()
        alerts = query.order_by(Alert.created_at.desc()).offset(skip).limit(limit).all()
        return alerts, total

    def mark_as_read(self, alert_ids: list[int], user_id: int, user_role: str) -> int:
        """Mark specific alerts as read, ensuring the user actually has access to them."""
        # Find which of the requested IDs the user is allowed to see
        valid_alerts = self._db.query(Alert.id).filter(
            Alert.id.in_(alert_ids),
            or_(
                Alert.target_user_id == user_id,
                Alert.target_role == user_role,
                (Alert.target_user_id.is_(None) & Alert.target_role.is_(None))
            )
        ).all()

        valid_ids = [a[0] for a in valid_alerts]
        if not valid_ids:
            return 0

        updated = self._db.query(Alert).filter(Alert.id.in_(valid_ids)).update(
            {"is_read": True}, synchronize_session=False
        )
        self._db.commit()
        return updated
