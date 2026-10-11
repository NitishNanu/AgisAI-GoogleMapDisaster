"""Prediction Service Unit Tests."""

from unittest.mock import MagicMock, patch

from app.modules.prediction.schemas import (
    DisasterSpreadPredictionRequest,
    ResourceOptimizationRequest,
    RLRecommendationRequest,
)
from app.modules.prediction.service import PredictionService


class TestLegacySpreadPrediction:
    def test_fire_spread(self) -> None:
        req = DisasterSpreadPredictionRequest(
            disaster_id=1,
            disaster_type="FIRE",
            severity="CRITICAL",
            latitude=30.7333,
            longitude=76.7794,
            wind_speed_kmh=20.0,
            forecast_hours=3,
        )
        res = PredictionService.predict_disaster_spread(req)
        assert res.disaster_id == 1
        assert res.disaster_type == "FIRE"
        assert res.confidence_score > 0.8
        assert len(res.zones) == 2

    def test_flood_spread(self) -> None:
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
        assert res.disaster_type == "FLOOD"
        assert res.forecast_hours == 6

    def test_spread_direction_is_valid(self) -> None:
        req = DisasterSpreadPredictionRequest(
            disaster_id=3,
            disaster_type="GAS_LEAK",
            severity="MEDIUM",
            latitude=30.7150,
            longitude=76.7600,
            wind_speed_kmh=15.0,
            forecast_hours=2,
        )
        res = PredictionService.predict_disaster_spread(req)
        assert 0 <= res.spread_direction_degrees <= 360

    def test_outer_zone_larger_than_inner(self) -> None:
        req = DisasterSpreadPredictionRequest(
            disaster_id=4,
            disaster_type="WILDFIRE",
            severity="HIGH",
            latitude=30.7000,
            longitude=76.8000,
            wind_speed_kmh=40.0,
            forecast_hours=4,
        )
        res = PredictionService.predict_disaster_spread(req)
        assert res.zones[1].radius_meters > res.zones[0].radius_meters

    def test_critical_severity_spreads_faster_than_low(self) -> None:
        base = {
            "disaster_id": 5,
            "disaster_type": "FIRE",
            "latitude": 30.7,
            "longitude": 76.7,
            "wind_speed_kmh": 10.0,
            "forecast_hours": 3,
        }

        crit_res = PredictionService.predict_disaster_spread(
            DisasterSpreadPredictionRequest(**{**base, "severity": "CRITICAL"})
        )
        low_res = PredictionService.predict_disaster_spread(
            DisasterSpreadPredictionRequest(**{**base, "severity": "LOW"})
        )
        assert crit_res.zones[0].radius_meters > low_res.zones[0].radius_meters


class TestResourceOptimization:
    def test_optimization_with_no_incidents_returns_empty(self) -> None:
        """Optimization with non-existent incident IDs should return empty assignments."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        mock_db = MagicMock()

        with patch("app.modules.prediction.service.IncidentRepository", return_value=mock_repo), \
             patch("app.modules.prediction.service.Session"):
            req = ResourceOptimizationRequest(incident_ids=[9999])
            result = PredictionService.optimize_allocation(mock_db, req)
            assert result.total_incidents_covered == 0
            assert result.assignments == []


class TestRLRecommendation:
    def test_critical_incident_recommends_dispatch(self) -> None:
        """CRITICAL incident should always recommend DISPATCH_TEAM first."""
        mock_incident = MagicMock()
        mock_incident.id = 1
        mock_incident.severity = "CRITICAL"
        mock_incident.status = "REPORTED"
        mock_incident.disaster_type = "FIRE"
        mock_incident.affected_radius_meters = 800.0

        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = mock_incident
        mock_db = MagicMock()

        with patch("app.modules.prediction.service.IncidentRepository", return_value=mock_repo):
            req = RLRecommendationRequest(
                incident_id=1,
                active_incident_count=1,
                available_team_count=5,
                shelter_capacity_percent=30.0,
            )
            res = PredictionService.get_rl_recommendation(mock_db, req)
            assert res.incident_id == 1
            assert len(res.recommended_actions) > 0
            action_types = [a.action_type for a in res.recommended_actions]
            assert "DISPATCH_TEAM" in action_types

    def test_shelter_pressure_recommends_open_shelter(self) -> None:
        """High shelter utilization should recommend OPEN_SHELTER."""
        mock_incident = MagicMock()
        mock_incident.id = 2
        mock_incident.severity = "MEDIUM"
        mock_incident.status = "REPORTED"
        mock_incident.disaster_type = "FLOOD"
        mock_incident.affected_radius_meters = 500.0

        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = mock_incident
        mock_db = MagicMock()

        with patch("app.modules.prediction.service.IncidentRepository", return_value=mock_repo):
            req = RLRecommendationRequest(
                incident_id=2,
                active_incident_count=1,
                available_team_count=5,
                shelter_capacity_percent=90.0,  # High shelter pressure
            )
            res = PredictionService.get_rl_recommendation(mock_db, req)
            action_types = [a.action_type for a in res.recommended_actions]
            assert "OPEN_SHELTER" in action_types

    def test_state_vector_contains_expected_keys(self) -> None:
        mock_incident = MagicMock()
        mock_incident.id = 3
        mock_incident.severity = "LOW"
        mock_incident.status = "MONITORING"
        mock_incident.disaster_type = "OTHER"
        mock_incident.affected_radius_meters = 100.0

        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = mock_incident
        mock_db = MagicMock()

        with patch("app.modules.prediction.service.IncidentRepository", return_value=mock_repo):
            req = RLRecommendationRequest(
                incident_id=3,
                active_incident_count=2,
                available_team_count=3,
                shelter_capacity_percent=40.0,
                simulation_tick=15,
            )
            res = PredictionService.get_rl_recommendation(mock_db, req)
            vector = res.state_vector
            assert "incident_id" in vector
            assert "severity_encoded" in vector
            assert "active_incidents" in vector
            assert "available_teams" in vector
            assert "team_deficit" in vector
            assert "shelter_pressure" in vector
            assert "simulation_tick" in vector
            assert vector["simulation_tick"] == 15
