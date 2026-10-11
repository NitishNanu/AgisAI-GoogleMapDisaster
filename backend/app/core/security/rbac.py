from typing import Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.common.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_token
from app.database.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user_payload(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    """
    Extracts and validates token payload from Bearer header.
    """
    if not token:
        raise UnauthorizedException("Authentication token is missing.")
    return decode_token(token)


def get_current_user(
    payload: dict[str, Any] = Depends(get_current_user_payload),
    db: Session = Depends(get_db)
) -> User:
    """
    Retrieves currently authenticated User model from DB.
    """
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Invalid token subject.")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise UnauthorizedException("Authenticated user no longer exists.")

    return user


class RequireRole:
    """
    RBAC Authorization Dependency Guard.
    Usage: Depends(RequireRole(["ADMIN", "DISPATCHER", "COMMANDER"]))
    """
    def __init__(self, allowed_roles: list[str]) -> None:
        self.allowed_roles = [role.upper() for role in allowed_roles]

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        user_role = getattr(current_user, "role", "CITIZEN").upper()
        if user_role not in self.allowed_roles and "ADMIN" not in user_role:
            raise ForbiddenException(
                f"Role '{user_role}' is not authorized. Allowed roles: {self.allowed_roles}"
            )
        return current_user
