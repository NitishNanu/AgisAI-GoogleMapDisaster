import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.hospital.models import Hospital
from app.modules.incident.models import Incident


class TestWebSocketStream:
    def test_websocket_connection_and_ping(self, client: TestClient, commander_token: str):
        with client.websocket_connect(f"/ws/v1/stream?client_id=test-client-1&token={commander_token}") as ws:
            init_msg = ws.receive_json()
            assert init_msg["event"] == "connection_established"
            assert init_msg["client_id"] == "test-client-1"

            # Send ping
            ws.send_json({"action": "ping", "timestamp": "2026-08-26T21:00:00Z"})
            pong_msg = ws.receive_json()
            assert pong_msg["event"] == "pong"

            # Subscribe to simulation channel
            ws.send_json({"action": "subscribe", "channel": "simulation"})
            sub_msg = ws.receive_json()
            assert sub_msg["event"] == "subscription_confirmed"
            assert sub_msg["channel"] == "simulation"

    def test_websocket_rejects_unauthenticated(self, client: TestClient):
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/v1/stream?client_id=unauth-client"):
                pass


class TestWhatIfAnalysisEngine:
    def test_what_if_comparison_api(self, client: TestClient, commander_headers: dict):
        payload = {
            "name": "Dynamic AI Evacuation Plan",
            "strategy": "AI_DYNAMIC_EVACUATION",
            "ticks": 10,
            "seed": 100,
            "evacuation_speed_multiplier": 2.0,
            "panic_reduction_factor": 0.5,
        }
        res = client.post(
            "/api/v1/simulation/what-if/compare",
            json=payload,
            headers=commander_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        comparison = data["data"]
        assert "baseline_scenario" in comparison
        assert "intervened_scenario" in comparison
        assert "casualty_reduction_count" in comparison
        assert "casualty_reduction_percentage" in comparison
        assert "executive_recommendation" in comparison
        assert len(comparison["baseline_scenario"]["timeline"]) == 10
        assert len(comparison["intervened_scenario"]["timeline"]) == 10

    def test_what_if_requires_auth(self, client: TestClient):
        res = client.post("/api/v1/simulation/what-if/compare", json={})
        assert res.status_code in (401, 403)


class TestSimulationReplayEngine:
    def test_replay_history_and_seek(self, client: TestClient, admin_headers: dict):
        # Run 2 ticks via API to generate replay history
        res1 = client.post("/api/v1/simulation/action", json={"action": "tick"}, headers=admin_headers)
        assert res1.status_code == 200
        res2 = client.post("/api/v1/simulation/action", json={"action": "tick"}, headers=admin_headers)
        assert res2.status_code == 200

        # Query replay history
        res_hist = client.get("/api/v1/simulation/replay/history", headers=admin_headers)
        assert res_hist.status_code == 200
        history_data = res_hist.json()["data"]
        assert isinstance(history_data, list)
        assert len(history_data) >= 2

        latest_tick = history_data[0]["tick"]

        # Seek specific tick
        res_seek = client.get(
            f"/api/v1/simulation/replay/tick/{latest_tick}",
            headers=admin_headers,
        )
        assert res_seek.status_code == 200
        snapshot = res_seek.json()["data"]
        assert snapshot["tick"] == latest_tick
        assert "safe_citizens" in snapshot

    def test_create_checkpoint(self, client: TestClient, admin_headers: dict):
        res = client.post(
            "/api/v1/simulation/replay/checkpoint",
            json={"name": "test_checkpoint_alpha"},
            headers=admin_headers,
        )
        assert res.status_code == 201
        assert res.json()["data"]["name"] == "test_checkpoint_alpha"


class TestReportingAndAudits:
    def test_incident_after_action_report(self, client: TestClient, db: Session, commander_headers: dict):
        # Create an incident
        incident = Incident(
            title="AAR Test Chemical Fire",
            disaster_type="FIRE",
            severity="HIGH",
            status="RESOLVED",
            latitude=30.7046,
            longitude=76.7985,
            estimated_affected_people=120,
            reported_by=999,
        )
        db.add(incident)
        db.commit()

        res = client.get(
            f"/api/v1/analytics/aar/incident/{incident.id}",
            headers=commander_headers,
        )
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["incident_id"] == incident.id
        assert data["disaster_type"] == "FIRE"
        assert "executive_summary" in data
        assert "lessons_learned" in data
        assert isinstance(data["lessons_learned"], list)
        assert data["estimated_affected_people"] == 120

    def test_hospital_readiness_audit(self, client: TestClient, db: Session, commander_headers: dict):
        hospital = Hospital(
            name="Audit Test Hospital",
            beds=200,
            icu_beds=30,
            oxygen_available=True,
            blood_bank_available=True,
            is_operational=True,
            latitude=30.7350,
            longitude=76.7750,
        )
        db.add(hospital)
        db.commit()

        res = client.get(
            "/api/v1/analytics/audit/hospitals",
            headers=commander_headers,
        )
        assert res.status_code == 200
        data = res.json()["data"]
        assert "total_hospitals" in data
        assert "total_beds_capacity" in data
        assert "oxygen_readiness_pct" in data
        assert len(data["facilities"]) >= 1

    def test_export_incidents_csv(self, client: TestClient, commander_headers: dict):
        res = client.get(
            "/api/v1/analytics/export/incidents/csv",
            headers=commander_headers,
        )
        assert res.status_code == 200
        assert "text/csv" in res.headers.get("content-type", "")
        assert "ID,Title,Disaster Type" in res.text
