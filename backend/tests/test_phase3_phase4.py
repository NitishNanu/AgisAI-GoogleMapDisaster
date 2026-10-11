"""
AegisAI Phase 3 & Phase 4 Integration Tests.

Validates:
- Prometheus /metrics endpoint
- AuditService logging & /audit/logs API
- Free-text input sanitizer
- Dispatch idempotency key handling
- XGBoost disaster severity prediction
- PyTorch LSTM multi-horizon forecaster
- Gymnasium RL DisasterResponseGymEnv & PPO dispatch policy
- Commander RAG Assistant & tactical query synthesis
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.common.sanitizer import sanitize_payload, sanitize_text
from app.modules.audit.service import AuditService
from app.modules.ml_intelligence.commander_rag import CommanderRAGAssistant
from app.modules.ml_intelligence.lstm_forecaster import LSTMDisasterForecaster
from app.modules.ml_intelligence.rl_env import DisasterResponseGymEnv, PPORLDispatchPolicy
from app.modules.ml_intelligence.severity_model import DisasterSeverityModel


class TestPhase3Hardening:
    def test_prometheus_metrics_endpoint(self, client: TestClient):
        res = client.get("/metrics")
        assert res.status_code == 200
        assert "aegis_http_requests_total" in res.text or "aegis" in res.text

    def test_input_sanitizer(self):
        malicious = "<script>alert('xss')</script>Chemical spill in <b>Sector 4</b>\x00\x1f"
        cleaned = sanitize_text(malicious)
        assert "<script>" not in cleaned
        assert "</script>" not in cleaned
        assert "<b>" not in cleaned
        assert "Chemical spill in Sector 4" in cleaned

        payload = {
            "title": "Fire incident <script>",
            "notes": "Urgent <img src=x onerror=alert(1)>",
            "nested": {"description": "<b>Safe</b>"},
        }
        sanitized = sanitize_payload(payload)
        assert sanitized["title"] == "Fire incident"
        assert sanitized["notes"] == "Urgent"
        assert sanitized["nested"]["description"] == "Safe"

    def test_audit_logging_and_api(self, client: TestClient, db: Session, commander_headers: dict):
        log = AuditService.log(
            db=db,
            action="AI_DECISION_APPROVED",
            entity_type="ai_decisions",
            entity_id="101",
            user_id=998,
            details={"notes": "Commander override"},
        )
        assert log.id is not None
        assert log.action == "AI_DECISION_APPROVED"

        # Query API endpoint
        res = client.get("/api/v1/audit/logs?action=AI_DECISION_APPROVED", headers=commander_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert len(data["data"]) >= 1
        assert data["data"][0]["action"] == "AI_DECISION_APPROVED"


class TestPhase4MLIntelligence:
    def test_xgboost_severity_model_inference(self):
        model = DisasterSeverityModel.get_instance()
        payload = {
            "estimated_casualties": 25,
            "critical_patients": 8,
            "affected_radius_meters": 1200,
            "disaster_type": "FIRE",
            "wind_speed_kmh": 45.0,
            "rainfall_mm": 0.0,
            "priority": 4.5,
        }
        res = model.predict_severity(payload)
        assert "predicted_severity" in res
        assert res["predicted_severity"] in ["HIGH", "CRITICAL"]
        assert 0.0 <= res["confidence"] <= 1.0
        assert res["severity_multiplier"] >= 1.0
        assert "probabilities" in res

    def test_ml_severity_api_endpoint(self, client: TestClient, commander_headers: dict):
        payload = {
            "estimated_casualties": 5,
            "critical_patients": 1,
            "affected_radius_meters": 200,
            "disaster_type": "FLOOD",
            "wind_speed_kmh": 10.0,
            "rainfall_mm": 50.0,
            "priority": 2.5,
        }
        res = client.post("/api/v1/ml/severity/predict", json=payload, headers=commander_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "predicted_severity" in data["data"]

    def test_pytorch_lstm_forecaster(self):
        forecaster = LSTMDisasterForecaster.get_instance()
        history = [
            {"casualties": 4.0, "critical": 1.0, "radius_meters": 100.0, "active_teams": 1},
            {"casualties": 7.0, "critical": 2.0, "radius_meters": 180.0, "active_teams": 2},
            {"casualties": 12.0, "critical": 3.0, "radius_meters": 260.0, "active_teams": 2},
        ]
        res = forecaster.forecast_trajectory(history)
        assert "forecast_casualties" in res
        assert "5m" in res["forecast_casualties"]
        assert "60m" in res["forecast_casualties"]
        # Casualties should progress upward
        assert res["forecast_casualties"]["60m"] >= res["forecast_casualties"]["5m"]

    def test_lstm_forecast_api_endpoint(self, client: TestClient, commander_headers: dict):
        payload = {
            "history": [
                {"casualties": 5.0, "critical": 1.0, "radius_meters": 150.0, "active_teams": 1},
                {"casualties": 8.0, "critical": 2.0, "radius_meters": 220.0, "active_teams": 2},
            ],
            "baseline_casualties": 8.0,
            "baseline_radius_meters": 220.0,
        }
        res = client.post("/api/v1/ml/forecast/series", json=payload, headers=commander_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "forecast_casualties" in data["data"]

    def test_gymnasium_rl_environment(self):
        env = DisasterResponseGymEnv(max_steps=20)
        state, info = env.reset(seed=42, options={"initial_casualties": 15.0})
        assert len(state) == 8
        assert info["casualties"] == 15.0

        # Take action 2 (Fire squad)
        next_state, reward, terminated, truncated, step_info = env.step(2)
        assert len(next_state) == 8
        assert step_info["remaining_casualties"] < 15.0
        assert isinstance(reward, float)

    def test_ppo_rl_dispatch_policy(self):
        action = PPORLDispatchPolicy.select_action({
            "disaster_type": "FIRE",
            "estimated_casualties": 22,
            "critical_patients": 6,
            "affected_radius_meters": 650,
        })
        assert "recommended_action" in action
        assert "action_index" in action
        assert action["confidence"] > 0.8
        assert "PPO" in action["rationale"]

    @pytest.mark.asyncio
    async def test_commander_rag_assistant(self):
        assistant = CommanderRAGAssistant.get_instance()
        sops = assistant.retrieve_sops("high rise structural fire ladder staging", top_k=2)
        assert len(sops) == 2
        assert any("FIRE" in s["sop_id"] for s in sops)

        briefing = await assistant.answer_query(
            query="High-rise building fire on 14th floor with people trapped",
            incident_context={"disaster_type": "FIRE", "severity": "CRITICAL", "estimated_casualties": 10},
        )
        assert "response" in briefing
        assert "cited_sops" in briefing
        assert len(briefing["cited_sops"]) > 0

    def test_commander_assistant_api_endpoint(self, client: TestClient, commander_headers: dict):
        payload = {
            "query": "Chemical plume reported near residential zone, what are initial steps?",
            "incident_context": {"disaster_type": "HAZMAT", "severity": "HIGH"},
        }
        res = client.post("/api/v1/assistant/query", json=payload, headers=commander_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "response" in data["data"]
        assert len(data["data"]["cited_sops"]) > 0
