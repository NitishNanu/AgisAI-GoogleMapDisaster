"""
AegisAI Auth Module â€” Authentication Domain Service.

Encapsulates all authentication business logic. The service layer:
- Never accesses the DB directly â€” delegates to UserRepository
- Raises domain exceptions (not HTTP exceptions)
- Remains fully unit-testable with a mocked repository
"""

from sqlalchemy.orm import Session

from app.core.common.exceptions import ConflictException, EntityNotFoundException, UnauthorizedException
from app.core.common.logging import logger
from app.core.config.settings import settings
from app.core.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import TokenResponse, UserRegisterRequest


class AuthService:
    """
    Authentication & Identity Domain Service.

    Handles user registration, credential verification, and JWT token lifecycle.
    All methods are static â€” services are stateless by design.
    """

    @staticmethod
    def register_user(db: Session, request: UserRegisterRequest) -> User:
        """
        Register a new platform user.

        Validates email uniqueness, hashes the password, and persists the user.

        Args:
            db: Active database session.
            request: Validated registration payload.

        Returns:
            Newly created User ORM instance.

        Raises:
            ConflictException: If the email address is already registered.
        """
        repo = UserRepository(db)

        # Check for duplicate email before attempting insert
        if repo.get_by_email(request.email):
            raise ConflictException(
                f"An account with email '{request.email}' already exists.",
                details={"email": request.email},
            )

        user = repo.create(
            name=request.name,
            email=request.email,
            password_hash=hash_password(request.password),
            role="CITIZEN",  # always CITIZEN — ADMIN assigns roles after registration
        )

        logger.info(
            "user_registered",
            user_id=user.id,
            email=user.email,
            role=user.role,
        )
        return user

    @staticmethod
    def login_user(db: Session, email: str, password: str) -> TokenResponse:
        """
        Authenticate a user and return JWT token pair.

        Args:
            db: Active database session.
            email: Submitted email address.
            password: Plain-text password to verify.

        Returns:
            TokenResponse with access + refresh tokens.

        Raises:
            UnauthorizedException: If credentials are invalid.
        """
        repo = UserRepository(db)
        user = repo.get_by_email(email)

        # Use constant-time comparison to avoid timing attacks
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedException("Invalid email or password.")

        if not user.is_active:
            raise UnauthorizedException("Account is deactivated. Contact an administrator.")

        access_token = create_access_token(subject=user.id, role=user.role)
        refresh_token = create_refresh_token(subject=user.id)

        logger.info("user_login_success", user_id=user.id, email=user.email, role=user.role)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user_id=user.id,
            email=user.email,
            role=user.role,
            expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )

    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str) -> TokenResponse:
        """
        Issue a new access + refresh token pair from a valid refresh token.

        Args:
            db: Active database session.
            refresh_token: Signed refresh JWT string.

        Returns:
            New TokenResponse with fresh tokens.

        Raises:
            UnauthorizedException: If the token is invalid or not a refresh type.
            EntityNotFoundException: If the user no longer exists.
        """
        payload = decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise UnauthorizedException("Provided token is not a refresh token.")

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise UnauthorizedException("Refresh token is missing subject claim.")

        repo = UserRepository(db)
        user = repo.get_by_id(int(user_id_str))
        if user is None:
            raise EntityNotFoundException("User", user_id_str)

        if not user.is_active:
            raise UnauthorizedException("Account is deactivated.")

        new_access = create_access_token(subject=user.id, role=user.role)
        new_refresh = create_refresh_token(subject=user.id)

        logger.info("tokens_refreshed", user_id=user.id)

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer",
            user_id=user.id,
            email=user.email,
            role=user.role,
            expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        )
