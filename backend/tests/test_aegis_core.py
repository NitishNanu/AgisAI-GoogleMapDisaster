"""
AegisAI Core Unit Tests.

Tests the foundational layers of the platform:
  - AppSettings configuration validation
  - ApiResponse envelope construction
  - JWT token lifecycle (create, decode, expiry)
  - Domain exception hierarchy and HTTP codes
  - Digital Twin Engine tick processing
  - PredictionService legacy spread model
"""


from app.core.common.exceptions import (
    ConflictException,
    EntityNotFoundException,
    ForbiddenException,
    ValidationException,
)
from app.core.common.response import ApiResponse
from app.core.config.settings import settings
from app.core.security.jwt import create_access_token, create_refresh_token, decode_token

# --- Settings ----------------------------------------------------------------

class TestSettings:
    def test_project_name_is_set(self):
        assert settings.PROJECT_NAME is not None
        assert len(settings.PROJECT_NAME) > 0

    def test_api_version_prefix(self):
        assert settings.API_V1 == "/api/v1"

    def test_database_url_has_driver(self):
        assert "postgresql" in settings.DATABASE_URL

    def test_jwt_secret_is_not_empty(self):
        assert settings.SECRET_KEY is not None
        assert len(settings.SECRET_KEY) >= 32

    def test_environment_field_exists(self):
        assert settings.ENVIRONMENT in ("development", "staging", "production", "testing")


# --- ApiResponse Envelope ----------------------------------------------------

class TestApiResponse:
    def test_ok_response(self):
        res = ApiResponse.ok(data={"key": "value"}, message="Test OK")
        assert res.success is True
        assert res.status_code == 200
        assert res.data == {"key": "value"}
        assert res.message == "Test OK"
        assert res.error is None

    def test_fail_response(self):
        res = ApiResponse.fail(message="Something failed", status_code=400)
        assert res.success is False
        assert res.status_code == 400
        assert res.data is None

    def test_created_response(self):
        res = ApiResponse.created(data={"id": 1}, message="Resource created")
        assert res.success is True
        assert res.status_code == 201

    def test_paginated_response(self):
        items = [{"id": i} for i in range(5)]
        res = ApiResponse.paginated(
            data=items, total=100, page=2, page_size=5
        )
        assert res.success is True
        assert len(res.data["items"]) == 5
        # Pagination metadata is present in the data dict
        assert res.data["total"] == 100
        assert res.data["page"] == 2


# --- JWT Token Lifecycle ------------------------------------------------------

class TestJWT:
    def test_access_token_creation(self):
        token = create_access_token(subject=42, role="COMMANDER")
        assert token is not None
        assert len(token) > 20

    def test_access_token_decode(self):
        token = create_access_token(subject=42, role="COMMANDER")
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["role"] == "COMMANDER"
        assert payload["type"] == "access"

    def test_refresh_token_decode(self):
        token = create_refresh_token(subject=42)
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["type"] == "refresh"

    def test_different_roles_produce_different_tokens(self):
        token_a = create_access_token(subject=1, role="ADMIN")
        token_c = create_access_token(subject=1, role="CITIZEN")
        assert token_a != token_c

    def test_different_subjects_produce_different_tokens(self):
        token1 = create_access_token(subject=1, role="ADMIN")
        token2 = create_access_token(subject=2, role="ADMIN")
        assert token1 != token2


# --- Exception Hierarchy -----------------------------------------------------

class TestDomainExceptions:
    def test_entity_not_found(self):
        exc = EntityNotFoundException(entity_name="Incident", entity_id=99)
        assert exc.status_code == 404
        assert "Incident" in exc.message
        assert "99" in exc.message

    def test_forbidden_exception(self):
        exc = ForbiddenException("You lack the required role.")
        assert exc.status_code == 403
        assert "required role" in exc.message

    def test_conflict_exception(self):
        exc = ConflictException("Resource already exists.")
        assert exc.status_code == 409

    def test_validation_exception(self):
        exc = ValidationException("Invalid severity level", details={"field": "severity"})
        assert exc.status_code == 422

    def test_exception_is_aegis_exception(self):
        from app.core.common.exceptions import AegisException
        exc = EntityNotFoundException("User", 1)
        assert isinstance(exc, AegisException)


# --- Digital Twin Engine ------------------------------------------------------

class TestDigitalTwinEngine:
    def test_engine_is_singleton(self):
        from app.modules.simulation.engine import DigitalTwinEngine
        e1 = DigitalTwinEngine()
        e2 = DigitalTwinEngine()
        assert e1 is e2

    def test_engine_has_citizens(self):
        from app.modules.simulation.engine import engine
        assert len(engine.citizens) > 0

    def test_engine_has_buildings(self):
        from app.modules.simulation.engine import engine
        assert len(engine.buildings) > 0

    def test_engine_has_roads(self):
        from app.modules.simulation.engine import engine
        assert len(engine.roads) > 0

    def test_tick_increments_count(self):
        import asyncio

        from app.modules.simulation.engine import engine
        before = engine.tick_count
        asyncio.run(engine.tick())
        assert engine.tick_count == before + 1

    def test_reset_returns_to_initial_state(self):
        from app.modules.simulation.engine import engine
        engine.force_add_disaster(30.7335, 76.7794, "HIGH")
        assert engine.active_disasters_count >= 1
        engine.reset()
        assert engine.tick_count == 0
        assert engine.active_disasters_count == 0

    def test_event_log_populated_after_tick(self):
        import asyncio

        from app.modules.simulation.engine import engine
        asyncio.run(engine.tick())
        events = engine.get_event_log()
        assert len(events) > 0


    def test_config_update(self):
        from app.modules.simulation.engine import engine
        from app.modules.simulation.schemas import SimulationConfig
        config = SimulationConfig(weather_multiplier=2.5, traffic_multiplier=1.5)
        engine.update_config(config)
        assert engine.config["weather_multiplier"] == 2.5
        assert engine.config["traffic_multiplier"] == 1.5
        # Reset to defaults
        engine.update_config(SimulationConfig())


# --- Prediction Service (Legacy) ---------------------------------------------

class TestPredictionService:
    def test_predict_disaster_spread_fire(self):
        from app.modules.prediction.schemas import DisasterSpreadPredictionRequest
        from app.modules.prediction.service import PredictionService

        req = DisasterSpreadPredictionRequest(
            disaster_id=1,
            disaster_type="FIRE",
            severity="CRITICAL",
            latitude=30.7333,
            longitude=76.7794,
            wind_speed_kmh=25.0,
            forecast_hours=3,
        )
        res = PredictionService.predict_disaster_spread(req)
        assert res.disaster_id == 1
        assert res.confidence_score > 0.8
        assert len(res.zones) == 2
        assert res.zones[0].risk_level == "HIGH"
        assert res.zones[1].risk_level == "MEDIUM"

    def test_predict_disaster_spread_flood(self):
        from app.modules.prediction.schemas import DisasterSpreadPredictionRequest
        from app.modules.prediction.service import PredictionService

        req = DisasterSpreadPredictionRequest(
            disaster_id=2,
            disaster_type="FLOOD",
            severity="HIGH",
            latitude=30.7355,
            longitude=76.7900,
            wind_speed_kmh=0.0,
            forecast_hours=6,
        )
        res = PredictionService.predict_disaster_spread(req)
        assert res.disaster_id == 2
        assert res.disaster_type == "FLOOD"
        assert len(res.zones) == 2

    def test_spread_zones_have_required_fields(self):
        from app.modules.prediction.schemas import DisasterSpreadPredictionRequest
        from app.modules.prediction.service import PredictionService

        req = DisasterSpreadPredictionRequest(
            disaster_id=3,
            disaster_type="GAS_LEAK",
            severity="MEDIUM",
            latitude=30.7150,
            longitude=76.7600,
            wind_speed_kmh=10.0,
            forecast_hours=2,
        )
        res = PredictionService.predict_disaster_spread(req)
        for zone in res.zones:
            assert zone.radius_meters > 0
            assert zone.risk_level in ("HIGH", "MEDIUM", "LOW")
            assert zone.estimated_impacted_population >= 0
            assert zone.recommended_action
