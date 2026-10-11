"""
AegisAI Test Suite â€” pytest Configuration and Shared Fixtures.

Provides reusable fixtures for all test modules:
  - `client`: A TestClient for the FastAPI app with DB overridden to SQLite
  - `db`: An in-memory SQLite session for unit tests
  - `admin_token`: A pre-minted JWT for an ADMIN-role user
  - `commander_token`: A pre-minted JWT for a COMMANDER-role user
  - `citizen_token`: A pre-minted JWT for a CITIZEN-role user
  - `auth_header`: Helper fixture producing Authorization header dicts

Design:
  The SQLite override uses a separate StaticPool engine so tests never
  touch the real PostgreSQL database. GeoAlchemy2 spatial columns are
  tested at the service/schema level only (not at the DB level in SQLite).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "JSON"


try:
    import geoalchemy2.admin.dialects.sqlite as sqlite_admin
    from geoalchemy2.types import Geography, Geometry

    @compiles(Geometry, "sqlite")
    @compiles(Geography, "sqlite")
    def compile_geom_sqlite(type_, compiler, **kw):
        return "TEXT"

    # Stub out the SQLite spatial index creation to prevent "no such function: CreateSpatialIndex"
    sqlite_admin.create_spatial_index = lambda *args, **kwargs: None
except ImportError:
    pass


from app.core.database.base import Base
from app.core.database.session import get_db
from app.core.security.jwt import create_access_token
from app.main import app

# â”€â”€â”€ Test Database Setup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# In-memory SQLite â€” no PostGIS, used only for unit testing non-spatial code.
# Spatial features are tested via integration tests against a real PostGIS DB.
SQLITE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def register_sqlite_spatial_stubs(dbapi_connection, connection_record):
    """Register spatial stub functions so SQLite can execute GeoAlchemy2 queries."""
    dbapi_connection.create_function("ST_GeogFromText", 1, lambda x: x)
    dbapi_connection.create_function("ST_GeomFromText", 1, lambda x: x)
    dbapi_connection.create_function("ST_AsText", 1, lambda x: str(x) if x else None)
    dbapi_connection.create_function("AsBinary", 1, lambda x: x.encode() if isinstance(x, str) else x)
    dbapi_connection.create_function("ST_AsBinary", 1, lambda x: x.encode() if isinstance(x, str) else x)
    dbapi_connection.create_function("ST_AsGeoJSON", 1, lambda x: str(x) if x else None)
    dbapi_connection.create_function("ST_Distance", 2, lambda a, b: 0.0)
    dbapi_connection.create_function("ST_DWithin", 3, lambda a, b, c: 1)


TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
)



def _override_get_db():
    """Replace the real DB dependency with an isolated SQLite test session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    """
    Create all tables in the in-memory SQLite DB once per test session.

    Imports all models to trigger their registration with Base.metadata.
    SQLite does not support PostGIS geometry columns — geometry columns
    are mapped to TEXT for testing purposes via the SQLite dialect.
    """
    # Import models to register with metadata
    import app.modules.ai.models  # noqa: F401
    import app.modules.audit.models  # noqa: F401
    import app.modules.auth.models  # noqa: F401
    import app.modules.hospital.models  # noqa: F401
    import app.modules.incident.models  # noqa: F401
    import app.modules.notification.models  # noqa: F401
    import app.modules.prediction.models  # noqa: F401
    import app.modules.resource.models  # noqa: F401
    import app.modules.scenario.models  # noqa: F401

    Base.metadata.create_all(bind=test_engine)

    # Seed synthetic users for the JWT fixtures
    with test_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, name, role, is_active) "
                "VALUES "
                "(999, 'admin@aegis.local', 'fakehash', 'Admin', 'ADMIN', 1), "
                "(998, 'commander@aegis.local', 'fakehash', 'Commander', 'COMMANDER', 1), "
                "(997, 'citizen@aegis.local', 'fakehash', 'Citizen', 'CITIZEN', 1), "
                "(996, 'dispatcher@aegis.local', 'fakehash', 'Dispatcher', 'DISPATCHER', 1)"
            )
        )

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db():
    """Provide an isolated SQLite test session per test function."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db):
    """
    FastAPI TestClient with the real DB dependency overridden.

    Each test gets a fresh, isolated SQLite session. The app's DB
    dependency is replaced with the test session factory for the
    duration of the test.
    """
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# â”€â”€â”€ JWT Token Fixtures â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.fixture(scope="session")
def admin_token() -> str:
    """Pre-minted JWT for a synthetic ADMIN user (ID=999)."""
    return create_access_token(subject=999, role="ADMIN")


@pytest.fixture(scope="session")
def commander_token() -> str:
    """Pre-minted JWT for a synthetic COMMANDER user (ID=998)."""
    return create_access_token(subject=998, role="COMMANDER")


@pytest.fixture(scope="session")
def citizen_token() -> str:
    """Pre-minted JWT for a synthetic CITIZEN user (ID=997)."""
    return create_access_token(subject=997, role="CITIZEN")


@pytest.fixture(scope="session")
def dispatcher_token() -> str:
    """Pre-minted JWT for a synthetic DISPATCHER user (ID=996)."""
    return create_access_token(subject=996, role="DISPATCHER")


@pytest.fixture()
def admin_headers(admin_token: str) -> dict:
    """Authorization header dict for ADMIN requests."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture()
def commander_headers(commander_token: str) -> dict:
    """Authorization header dict for COMMANDER requests."""
    return {"Authorization": f"Bearer {commander_token}"}


@pytest.fixture()
def citizen_headers(citizen_token: str) -> dict:
    """Authorization header dict for CITIZEN requests."""
    return {"Authorization": f"Bearer {citizen_token}"}
