"""
AegisAI Auth Module â€” Unit Tests for AuthService.

Tests the AuthService logic in complete isolation using an in-memory SQLite
database. No HTTP client or live services are required for these tests.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.common.exceptions import ConflictException, UnauthorizedException
from app.core.database.base import Base
from app.core.security.jwt import decode_token, verify_password
from app.modules.auth.models import User  # noqa: F401 â€” ensures table is created
from app.modules.auth.schemas import AuthRole, UserRegisterRequest
from app.modules.auth.service import AuthService

# ---------------------------------------------------------------------------
# Test Database Setup
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="function")
def db() -> Session:
    """Provide a fresh in-memory SQLite database for each test."""
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


# ---------------------------------------------------------------------------
# Registration Tests
# ---------------------------------------------------------------------------
class TestAuthServiceRegister:
    """Tests for AuthService.register_user()."""

    @pytest.mark.unit
    def test_register_user_success(self, db: Session) -> None:
        """Registering with valid data creates and persists the user."""
        request = UserRegisterRequest(
            name="Jane Smith",
            email="jane@example.com",
            password="SecurePass1",
            role=AuthRole.CITIZEN,
        )
        user = AuthService.register_user(db, request)

        assert user.id is not None
        assert user.name == "Jane Smith"
        assert user.email == "jane@example.com"
        assert user.role == "CITIZEN"
        assert user.is_active is True
        # Password must be stored as hash, never plain text
        assert user.password_hash != "SecurePass1"
        assert verify_password("SecurePass1", user.password_hash)

    @pytest.mark.unit
    def test_register_duplicate_email_raises_conflict(self, db: Session) -> None:
        """Re-registering the same email raises ConflictException."""
        request = UserRegisterRequest(
            name="Alice",
            email="alice@example.com",
            password="SecurePass1",
            role=AuthRole.CITIZEN,
        )
        AuthService.register_user(db, request)

        with pytest.raises(ConflictException) as exc_info:
            AuthService.register_user(db, request)

        assert exc_info.value.status_code == 409
        assert "alice@example.com" in exc_info.value.message

    @pytest.mark.unit
    def test_register_commander_role(self, db: Session) -> None:
        """Registering with COMMANDER role stores the correct role."""
        request = UserRegisterRequest(
            name="Bob Commander",
            email="bob@example.com",
            password="CommandPass1",
            role=AuthRole.COMMANDER,
        )
        user = AuthService.register_user(db, request)
        assert user.role == "COMMANDER"


# ---------------------------------------------------------------------------
# Login Tests
# ---------------------------------------------------------------------------
class TestAuthServiceLogin:
    """Tests for AuthService.login_user()."""

    @pytest.fixture(autouse=True)
    def seed_user(self, db: Session) -> None:
        """Create a test user before each login test."""
        request = UserRegisterRequest(
            name="Test User",
            email="testuser@example.com",
            password="TestPass123",
            role=AuthRole.DISPATCHER,
        )
        AuthService.register_user(db, request)

    @pytest.mark.unit
    def test_login_success_returns_tokens(self, db: Session) -> None:
        """Valid credentials return a token response with both tokens."""
        tokens = AuthService.login_user(db, "testuser@example.com", "TestPass123")

        assert tokens.access_token
        assert tokens.refresh_token
        assert tokens.token_type == "bearer"
        assert tokens.role == "DISPATCHER"

        # Validate access token payload
        payload = decode_token(tokens.access_token)
        assert payload["type"] == "access"
        assert payload["role"] == "DISPATCHER"

    @pytest.mark.unit
    def test_login_wrong_password_raises_unauthorized(self, db: Session) -> None:
        """Wrong password raises UnauthorizedException."""
        with pytest.raises(UnauthorizedException):
            AuthService.login_user(db, "testuser@example.com", "WrongPassword1")

    @pytest.mark.unit
    def test_login_nonexistent_email_raises_unauthorized(self, db: Session) -> None:
        """Unknown email raises UnauthorizedException (same message to avoid enumeration)."""
        with pytest.raises(UnauthorizedException):
            AuthService.login_user(db, "ghost@example.com", "SomePass1")


# ---------------------------------------------------------------------------
# Token Refresh Tests
# ---------------------------------------------------------------------------
class TestAuthServiceRefresh:
    """Tests for AuthService.refresh_access_token()."""

    @pytest.mark.unit
    def test_refresh_returns_new_tokens(self, db: Session) -> None:
        """Valid refresh token produces a fresh token pair."""
        request = UserRegisterRequest(
            name="Refresh User",
            email="refresh@example.com",
            password="RefreshPass1",
            role=AuthRole.CITIZEN,
        )
        AuthService.register_user(db, request)
        initial = AuthService.login_user(db, "refresh@example.com", "RefreshPass1")

        new_tokens = AuthService.refresh_access_token(db, initial.refresh_token)

        assert new_tokens.access_token
        assert new_tokens.refresh_token
        # New tokens should be different from the original pair
        assert new_tokens.access_token != initial.access_token

    @pytest.mark.unit
    def test_refresh_with_access_token_raises_unauthorized(self, db: Session) -> None:
        """Passing an access token to refresh endpoint raises UnauthorizedException."""
        request = UserRegisterRequest(
            name="Bad Refresh",
            email="badrefresh@example.com",
            password="BadRefresh1",
            role=AuthRole.CITIZEN,
        )
        AuthService.register_user(db, request)
        tokens = AuthService.login_user(db, "badrefresh@example.com", "BadRefresh1")

        with pytest.raises(UnauthorizedException):
            AuthService.refresh_access_token(db, tokens.access_token)
