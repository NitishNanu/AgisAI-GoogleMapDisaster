"""
AegisAI Notification Module â€” Pydantic v2 Schemas.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AlertCreate(BaseModel):
    """Schema to trigger a new alert."""

    title: str = Field(..., max_length=200)
    message: str
    severity: str = Field(..., pattern="^(INFO|WARNING|CRITICAL)$")
    target_role: str | None = None
    target_user_id: int | None = None


class AlertResponse(BaseModel):
    """Schema for returning alert details."""

    id: int
    title: str
    message: str
    severity: str
    target_role: str | None
    target_user_id: int | None
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MarkReadRequest(BaseModel):
    """Schema to mark alerts as read."""

    alert_ids: list[int] = Field(..., min_length=1)
