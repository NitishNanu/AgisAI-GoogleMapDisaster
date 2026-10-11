"""
AegisAI Auth Module â€” Pydantic v2 Schemas.

All schemas use strict Pydantic v2 field validators for production-level
input validation. Password strength is enforced at the schema level.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class AuthRole(str, Enum):
    """Valid platform roles â€” mirrors the DB check constraint."""

    ADMIN = "ADMIN"
    COMMANDER = "COMMANDER"
    DISPATCHER = "DISPATCHER"
    MEDIC = "MEDIC"
    RESPONDER = "RESPONDER"
    CITIZEN = "CITIZEN"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
class UserRegisterRequest(BaseModel):
    """Schema for user self-registration.

    NOTE: Role is NOT accepted here — all self-registrations create a CITIZEN.
    Only an ADMIN may assign or change roles after account creation.
    """

    name: str = Field(..., min_length=2, max_length=100, description="Full name")
    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password")

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        """Reject names that are only whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name must not be blank or whitespace only.")
        return stripped

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce minimum password complexity."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


class UserLoginRequest(BaseModel):
    """Schema for user credential login."""

    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")


class RefreshTokenRequest(BaseModel):
    """Schema for JWT token refresh."""

    refresh_token: str = Field(..., description="Valid refresh token")


class UpdateUserRoleRequest(BaseModel):
    """Schema for ADMIN role change."""

    role: AuthRole = Field(..., description="New role to assign")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------
class TokenResponse(BaseModel):
    """JWT token pair returned after successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    email: str
    role: str
    expires_in_minutes: int


class UserProfileResponse(BaseModel):
    """User profile data returned by /auth/me and user management endpoints."""

    id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """Paginated user list item."""

    id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
