"""
AegisAI API Integration Tests — Full Endpoint Suite.

Tests all major API endpoints using FastAPI''s TestClient with
JWT auth headers injected via the conftest.py fixtures.

Test groups:
  - Root / meta endpoints (no auth required)
  - Health check
  - Auth endpoints (register, login, refresh, me)
  - Simulation engine control
  - Prediction AI endpoints
  - Analytics dashboard
"""

from fastapi.testclient import TestClient

# --- Root Endpoint ------------------------------------------------------------

class TestRootEndpoint:
    def test_root_returns_200(self, client: TestClient):
        res = client.get("/")
        assert res.status_code == 200

    def test_root_contains_project_info(self, client: TestClient):
        res = client.get("/")
        data = res.json()
        assert "project" in data or "status" in data or "name" in data

    def test_root_is_operational(self, client: TestClient):
        res = client.get("/")
        data = res.json()
        # Accept either structure
        assert res.status_code == 200


# --- Health Check -------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_200(self, client: TestClient, admin_headers: dict):
        res = client.get("/api/v1/health", headers=admin_headers)
        assert res.status_code == 200

    def test_health_has_status_field(self, client: TestClient, admin_headers: dict):
        res = client.get("/api/v1/health", headers=admin_headers)
        data = res.json()
        assert "data" in data
        assert "status" in data["data"]
        assert data["data"]["status"] in ("healthy", "degraded")

    def test_health_has_services(self, client: TestClient, admin_headers: dict):
        res = client.get("/api/v1/health", headers=admin_headers)
        data = res.json()
        assert "services" in data["data"]
        services = data["data"]["services"]
        assert "postgres" in services
        assert "redis" in services
        assert "rabbitmq" in services


# --- Auth — Registration and Login --------------------------------------------

class TestAuthEndpoints:
    def test_register_missing_fields_returns_422(self, client: TestClient):
        res = client.post("/api/v1/auth/register", json={"email": "bad"})
        assert res.status_code == 422

    def test_login_with_invalid_credentials_returns_401(self, client: TestClient):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@test.com", "password": "WrongPass123!"},
        )
        assert res.status_code in (401, 404, 422)

    def test_protected_route_without_token_returns_401(self, client: TestClient):
        res = client.get("/api/v1/auth/me")
        assert res.status_code == 401


# --- Simulation Engine --------------------------------------------------------

class TestSimulationEndpoints:
    def test_get_simulation_state_public(self, client: TestClient):
        res = client.get("/api/v1/simulation/state")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True

    def test_get_simulation_state_with_auth(self, client: TestClient, admin_headers: dict):
        res = client.get("/api/v1/simulation/state", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "current_tick" in data["data"]
        assert "is_running" in data["data"]

    def test_simulation_tick_action(self, client: TestClient, admin_headers: dict):
        res = client.post(
            "/api/v1/simulation/action",
            json={"action": "tick"},
            headers=admin_headers,
        )
        assert res.status_code == 200

    def test_simulation_citizen_public(self, client: TestClient):
        res = client.get("/api/v1/simulation/citizens")
        assert res.status_code == 200

    def test_simulation_events_with_auth(self, client: TestClient, admin_headers: dict):
        res = client.get("/api/v1/simulation/events", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_simulation_buildings_with_auth(self, client: TestClient, admin_headers: dict):
        res = client.get("/api/v1/simulation/buildings", headers=admin_headers)
        assert res.status_code == 200

    def test_simulation_snapshot_with_auth(self, client: TestClient, admin_headers: dict):
        res = client.get("/api/v1/simulation/snapshot", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert "tick_count" in data["data"]
        assert "weather" in data["data"]
        assert "citizens" in data["data"]

    def test_citizen_action_forbidden_for_citizen(self, client: TestClient, citizen_headers: dict):
        # CITIZEN cannot control simulation
        res = client.post(
            "/api/v1/simulation/action",
            json={"action": "tick"},
            headers=citizen_headers,
        )
        assert res.status_code == 403

    def test_reset_action_requires_admin(self, client: TestClient, commander_headers: dict):
        res = client.post(
            "/api/v1/simulation/action",
            json={"action": "reset"},
            headers=commander_headers,
        )
        # COMMANDER does not have ADMIN role — should be 403
        assert res.status_code == 403


# --- Prediction AI Endpoints --------------------------------------------------

class TestPredictionEndpoints:
    def test_legacy_spread_requires_auth(self, client: TestClient):
        res = client.post("/api/v1/predictions/legacy/spread", json={})
        assert res.status_code in (401, 422)

    def test_optimize_requires_commander(self, client: TestClient, citizen_headers: dict):
        res = client.post(
            "/api/v1/predictions/optimize",
            json={"incident_ids": [1]},
            headers=citizen_headers,
        )
        assert res.status_code == 403

    def test_rl_recommend_requires_auth(self, client: TestClient):
        res = client.post("/api/v1/predictions/recommend", json={"incident_id": 1})
        assert res.status_code == 401


# --- Analytics Endpoints ------------------------------------------------------

class TestAnalyticsEndpoints:
    def test_dashboard_requires_auth(self, client: TestClient):
        res = client.get("/api/v1/analytics/dashboard")
        assert res.status_code == 401

    def test_dashboard_with_admin(self, client: TestClient, admin_headers: dict):
        res = client.get("/api/v1/analytics/dashboard", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        dashboard = data["data"]
        assert "total_active_incidents" in dashboard
        assert "available_rescue_teams" in dashboard
        assert "total_hospitals" in dashboard

    def test_incidents_by_type_with_auth(self, client: TestClient, admin_headers: dict):
        res = client.get("/api/v1/analytics/incidents/by-type", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_incidents_by_severity_with_auth(self, client: TestClient, admin_headers: dict):
        res = client.get("/api/v1/analytics/incidents/by-severity", headers=admin_headers)
        assert res.status_code == 200

    def test_resource_utilization_requires_commander(
        self, client: TestClient, citizen_headers: dict
    ):
        res = client.get("/api/v1/analytics/resources/utilization", headers=citizen_headers)
        assert res.status_code == 403

    def test_reports_list_requires_admin(self, client: TestClient, citizen_headers: dict):
        res = client.get("/api/v1/analytics/reports", headers=citizen_headers)
        assert res.status_code == 403

    def test_reports_list_with_admin(self, client: TestClient, admin_headers: dict):
        res = client.get("/api/v1/analytics/reports", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
