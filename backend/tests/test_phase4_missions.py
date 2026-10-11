"""
RescueNet AI — Phase 4 Mission Control & Smart Dispatch Test Suite.

Comprehensive tests covering:
- PostGIS Top-K candidate selection and availability filtering
- Multi-factor response scoring and vehicle compatibility
- Smart dispatch ranking and OSRM top-K candidate bounds
- Transaction-safe dispatching and duplicate mission prevention
- Mission state machine valid & invalid transitions
- Timestamp tracking (started_at, completed_at)
- Team status synchronization and release
- Disaster lifecycle synchronization
- Mission Control endpoints (/missions, /assignments/{id}/status, /disasters/...)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.common.exceptions import ConflictException, ValidationException
from app.modules.incident.models import Incident
from app.modules.resource.enums import TeamStatus, VehicleType
from app.modules.resource.models import RescueTeam
from app.services.assignment_service import AssignmentService
from app.services.geospatial_service import GeospatialService
from app.services.response_scoring_service import ResponseScoringService
from app.services.smart_dispatch_service import SmartDispatchService


# ---------------------------------------------------------------------------
# Test Group 1: Response Scoring
# ---------------------------------------------------------------------------
class TestResponseScoring:
    def test_vehicle_suitability_fire(self):
        score_truck = ResponseScoringService.get_vehicle_suitability_score("FIRE", "FIRE_TRUCK")
        score_van = ResponseScoringService.get_vehicle_suitability_score("FIRE", "RESCUE_VAN")
        score_amb = ResponseScoringService.get_vehicle_suitability_score("FIRE", "AMBULANCE")

        assert score_truck == 100.0
        assert score_van == 60.0
        assert score_amb == 30.0

    def test_vehicle_suitability_accident(self):
        score_amb = ResponseScoringService.get_vehicle_suitability_score("ACCIDENT", "AMBULANCE")
        score_truck = ResponseScoringService.get_vehicle_suitability_score("ACCIDENT", "FIRE_TRUCK")

        assert score_amb == 100.0
        assert score_truck == 50.0

    def test_composite_score_calculation(self):
        # High suitability (100), close distance (5km), low ETA (6min), available (100)
        score = ResponseScoringService.calculate_score(
            disaster_type="FIRE",
            vehicle_type="FIRE_TRUCK",
            distance_km=5.0,
            eta_minutes=6.0,
            status="AVAILABLE",
        )
        assert 80.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# Test Group 2: Geospatial Top-K Candidate Selection
# ---------------------------------------------------------------------------
class TestGeospatialCandidates:
    def test_candidate_limit_and_availability_filter(self, db: Session):
        # Create a disaster
        disaster = Incident(
            title="Test Candidate Disaster",
            disaster_type="FIRE",
            severity="HIGH",
            status="ACTIVE",
            latitude=30.7333,
            longitude=76.7794,
            reported_by=999,
        )
        db.add(disaster)
        db.commit()

        # Create 10 available teams and 5 unavailable teams
        for i in range(10):
            team = RescueTeam(
                team_name=f"Available Team {i}_{disaster.id}",
                vehicle_type=VehicleType.FIRE_TRUCK.value,
                members=6,
                status=TeamStatus.AVAILABLE.value,
                latitude=30.7300 + (i * 0.01),
                longitude=76.7700 + (i * 0.01),
            )
            db.add(team)

        for i in range(5):
            busy_team = RescueTeam(
                team_name=f"Busy Team {i}_{disaster.id}",
                vehicle_type=VehicleType.FIRE_TRUCK.value,
                members=6,
                status=TeamStatus.DISPATCHED.value,
                latitude=30.7300,
                longitude=76.7700,
            )
            db.add(busy_team)

        db.commit()

        # Query top 5 candidates
        candidates = GeospatialService.find_candidate_rescue_teams(
            db, disaster_id=disaster.id, limit=5
        )

        assert len(candidates) == 5
        # Ensure all returned candidates are AVAILABLE
        for team, dist in candidates:
            assert team.status == "AVAILABLE"
            assert dist >= 0

        # Ensure ordered by distance ascending
        distances = [dist for _, dist in candidates]
        assert distances == sorted(distances)

    @pytest.mark.asyncio
    async def test_osrm_candidate_call_limit_with_100_teams(self, db: Session, monkeypatch):
        """Verify that when 100 teams exist, OSRM is called strictly <= limit (5) times."""
        from app.routing.osrm import OSRMService

        disaster = Incident(
            title="Large Scale Candidate Disaster",
            disaster_type="FIRE",
            severity="HIGH",
            status="ACTIVE",
            latitude=30.7333,
            longitude=76.7794,
            reported_by=999,
        )
        db.add(disaster)
        db.commit()

        for i in range(100):
            team = RescueTeam(
                team_name=f"Scale Team {i}_{disaster.id}",
                vehicle_type=VehicleType.FIRE_TRUCK.value,
                members=4,
                status=TeamStatus.AVAILABLE.value,
                latitude=30.7000 + (i * 0.001),
                longitude=76.7000 + (i * 0.001),
            )
            db.add(team)
        db.commit()

        osrm_calls = []

        async def mock_get_route(start_lat, start_lon, end_lat, end_lon):
            osrm_calls.append((start_lat, start_lon))
            return {
                "distance_km": 4.5,
                "duration_minutes": 7.0,
                "geometry": {"type": "LineString", "coordinates": []},
            }

        monkeypatch.setattr(OSRMService, "get_route", mock_get_route)

        ranked = await SmartDispatchService.get_recommended_teams(
            db=db, disaster_id=disaster.id, limit=5
        )

        assert len(ranked) == 5
        # Crucial performance rule verification:
        assert len(osrm_calls) == 5



# ---------------------------------------------------------------------------
# Test Group 3: Dispatch Transaction Safety & Prevention
# ---------------------------------------------------------------------------
class TestDispatchTransactionSafety:
    def test_successful_dispatch(self, db: Session):
        disaster = Incident(
            title="Dispatchable Incident",
            disaster_type="FIRE",
            severity="CRITICAL",
            status="ACTIVE",
            latitude=30.7046,
            longitude=76.7985,
            reported_by=999,
        )
        team = RescueTeam(
            team_name=f"Dispatch Team {disaster.id}",
            vehicle_type=VehicleType.FIRE_TRUCK.value,
            members=8,
            status="AVAILABLE",
            latitude=30.7100,
            longitude=76.7900,
        )
        db.add_all([disaster, team])
        db.commit()

        assignment = AssignmentService.create_assignment(
            db=db,
            incident_id=disaster.id,
            team_id=team.id,
            dispatched_by=999,
            notes="Initial dispatch",
            distance_km=3.2,
            estimated_arrival_minutes=5.0,
        )

        assert assignment.id is not None
        assert assignment.status == "ASSIGNED"
        # Team updated to DISPATCHED
        assert team.status == "DISPATCHED"
        # Disaster updated to RESPONDING
        assert disaster.status == "RESPONDING"

    def test_prevent_dispatch_unavailable_team(self, db: Session):
        disaster = Incident(
            title="Incident A",
            disaster_type="FIRE",
            severity="HIGH",
            status="ACTIVE",
            latitude=30.7046,
            longitude=76.7985,
            reported_by=999,
        )
        busy_team = RescueTeam(
            team_name=f"Busy Unit {disaster.id}",
            vehicle_type=VehicleType.FIRE_TRUCK.value,
            members=6,
            status="DISPATCHED",
            latitude=30.7100,
            longitude=76.7900,
        )
        db.add_all([disaster, busy_team])
        db.commit()

        with pytest.raises(ConflictException):
            AssignmentService.create_assignment(
                db=db,
                incident_id=disaster.id,
                team_id=busy_team.id,
                dispatched_by=999,
            )

    def test_prevent_duplicate_active_dispatch(self, db: Session):
        disaster = Incident(
            title="Incident Double Dispatch",
            disaster_type="FIRE",
            severity="HIGH",
            status="ACTIVE",
            latitude=30.7046,
            longitude=76.7985,
            reported_by=999,
        )
        team1 = RescueTeam(
            team_name=f"Team 1 {disaster.id}",
            vehicle_type=VehicleType.FIRE_TRUCK.value,
            members=6,
            status="AVAILABLE",
            latitude=30.7100,
            longitude=76.7900,
        )
        team2 = RescueTeam(
            team_name=f"Team 2 {disaster.id}",
            vehicle_type=VehicleType.RESCUE_VAN.value,
            members=4,
            status="AVAILABLE",
            latitude=30.7200,
            longitude=76.7800,
        )
        db.add_all([disaster, team1, team2])
        db.commit()

        # First dispatch succeeds
        AssignmentService.create_assignment(
            db=db,
            incident_id=disaster.id,
            team_id=team1.id,
            dispatched_by=999,
        )

        # Second dispatch to the same disaster while active must be rejected
        with pytest.raises(ConflictException):
            AssignmentService.create_assignment(
                db=db,
                incident_id=disaster.id,
                team_id=team2.id,
                dispatched_by=999,
            )


# ---------------------------------------------------------------------------
# Test Group 4: Mission State Machine & Lifecycle
# ---------------------------------------------------------------------------
class TestMissionStateMachine:
    def test_full_lifecycle_and_timestamps(self, db: Session):
        disaster = Incident(
            title="Lifecycle Incident",
            disaster_type="FLOOD",
            severity="CRITICAL",
            status="ACTIVE",
            latitude=30.7415,
            longitude=76.7685,
            reported_by=999,
        )
        team = RescueTeam(
            team_name=f"Lifecycle Team {disaster.id}",
            vehicle_type=VehicleType.RESCUE_VAN.value,
            members=6,
            status="AVAILABLE",
            latitude=30.7350,
            longitude=76.7820,
        )
        db.add_all([disaster, team])
        db.commit()

        # 1. ASSIGNED
        assignment = AssignmentService.create_assignment(
            db=db,
            incident_id=disaster.id,
            team_id=team.id,
            dispatched_by=999,
        )
        assert assignment.status == "ASSIGNED"
        assert disaster.status == "RESPONDING"

        # 2. ASSIGNED -> DISPATCHED
        AssignmentService.update_assignment_status(db, assignment.id, "DISPATCHED")
        assert assignment.status == "DISPATCHED"

        # 3. DISPATCHED -> EN_ROUTE (sets started_at)
        AssignmentService.update_assignment_status(db, assignment.id, "EN_ROUTE")
        assert assignment.status == "EN_ROUTE"
        assert assignment.started_at is not None

        # 4. EN_ROUTE -> ARRIVED (team becomes ON_SCENE)
        AssignmentService.update_assignment_status(db, assignment.id, "ARRIVED")
        assert assignment.status == "ARRIVED"
        assert team.status == "ON_SCENE"

        # 5. ARRIVED -> COMPLETED (sets completed_at, releases team, resolves disaster)
        AssignmentService.update_assignment_status(db, assignment.id, "COMPLETED")
        assert assignment.status == "COMPLETED"
        assert assignment.completed_at is not None
        assert team.status == "AVAILABLE"
        assert disaster.status == "RESOLVED"

    def test_invalid_status_transitions_rejected(self, db: Session):
        disaster = Incident(
            title="Invalid Transition Incident",
            disaster_type="ACCIDENT",
            severity="MEDIUM",
            status="ACTIVE",
            latitude=30.6425,
            longitude=76.8173,
            reported_by=999,
        )
        team = RescueTeam(
            team_name=f"Invalid Trans Team {disaster.id}",
            vehicle_type=VehicleType.AMBULANCE.value,
            members=4,
            status="AVAILABLE",
            latitude=30.7400,
            longitude=76.7700,
        )
        db.add_all([disaster, team])
        db.commit()

        assignment = AssignmentService.create_assignment(
            db=db,
            incident_id=disaster.id,
            team_id=team.id,
            dispatched_by=999,
        )

        # ASSIGNED -> COMPLETED directly is invalid
        with pytest.raises(ValidationException):
            AssignmentService.update_assignment_status(db, assignment.id, "COMPLETED")

        # Advance to COMPLETED through valid steps
        AssignmentService.update_assignment_status(db, assignment.id, "EN_ROUTE")
        AssignmentService.update_assignment_status(db, assignment.id, "ARRIVED")
        AssignmentService.update_assignment_status(db, assignment.id, "COMPLETED")

        # COMPLETED -> EN_ROUTE is invalid
        with pytest.raises(ValidationException):
            AssignmentService.update_assignment_status(db, assignment.id, "EN_ROUTE")

    def test_cancellation_flow(self, db: Session):
        disaster = Incident(
            title="Cancelled Incident",
            disaster_type="GAS_LEAK",
            severity="HIGH",
            status="ACTIVE",
            latitude=30.6975,
            longitude=76.8042,
            reported_by=999,
        )
        team = RescueTeam(
            team_name=f"Cancel Team {disaster.id}",
            vehicle_type=VehicleType.HAZMAT_UNIT.value,
            members=5,
            status="AVAILABLE",
            latitude=30.7200,
            longitude=76.7600,
        )
        db.add_all([disaster, team])
        db.commit()

        assignment = AssignmentService.create_assignment(
            db=db,
            incident_id=disaster.id,
            team_id=team.id,
            dispatched_by=999,
        )
        assert disaster.status == "RESPONDING"
        assert team.status == "DISPATCHED"

        # Cancel mission
        AssignmentService.update_assignment_status(db, assignment.id, "CANCELLED")
        assert assignment.status == "CANCELLED"
        assert assignment.completed_at is not None
        # Team released to AVAILABLE
        assert team.status == "AVAILABLE"
        # Disaster returns to ACTIVE
        assert disaster.status == "ACTIVE"


# ---------------------------------------------------------------------------
# Test Group 5: Mission API Endpoints
# ---------------------------------------------------------------------------
class TestMissionAPIEndpoints:
    def test_get_missions_endpoint(self, client: TestClient, db: Session, commander_headers: dict):
        disaster = Incident(
            title="API Mission Disaster",
            disaster_type="FIRE",
            severity="HIGH",
            status="ACTIVE",
            latitude=30.7046,
            longitude=76.7985,
            reported_by=999,
        )
        db.add(disaster)
        db.commit()

        team = RescueTeam(
            team_name=f"API Mission Team {disaster.id}",
            vehicle_type=VehicleType.FIRE_TRUCK.value,
            members=6,
            status="AVAILABLE",
            latitude=30.7100,
            longitude=76.7900,
        )
        db.add(team)
        db.commit()


        # Dispatch
        res_disp = client.post(
            "/api/v1/assignments",
            json={
                "incident_id": disaster.id,
                "team_id": team.id,
                "estimated_arrival_minutes": 7.5,
                "notes": "Fast track",
            },
            headers=commander_headers,
        )
        assert res_disp.status_code == 201

        # Query /missions
        res_missions = client.get("/api/v1/missions")
        assert res_missions.status_code == 200
        data = res_missions.json()
        assert data["success"] is True
        assert data["count"] >= 1
        mission = next((m for m in data["data"] if m["disaster"]["id"] == disaster.id), None)
        assert mission is not None
        assert mission["status"] == "ASSIGNED"
        assert mission["disaster"]["title"] == "API Mission Disaster"
        assert mission["team"]["name"] == f"API Mission Team {disaster.id}"

    def test_update_assignment_status_api(self, client: TestClient, db: Session, commander_headers: dict):
        disaster = Incident(
            title="Status API Disaster",
            disaster_type="FIRE",
            severity="HIGH",
            status="ACTIVE",
            latitude=30.7046,
            longitude=76.7985,
            reported_by=999,
        )
        team = RescueTeam(
            team_name=f"Status API Team {disaster.id}",
            vehicle_type=VehicleType.FIRE_TRUCK.value,
            members=6,
            status="AVAILABLE",
            latitude=30.7100,
            longitude=76.7900,
        )
        db.add_all([disaster, team])
        db.commit()

        assignment = AssignmentService.create_assignment(
            db=db, incident_id=disaster.id, team_id=team.id, dispatched_by=999
        )

        # PUT /api/v1/assignments/{id}/status -> EN_ROUTE
        res = client.put(
            f"/api/v1/assignments/{assignment.id}/status",
            json={"status": "EN_ROUTE"},
            headers=commander_headers,
        )
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "EN_ROUTE"

        # Invalid transition returns 422 or 400
        res_invalid = client.put(
            f"/api/v1/assignments/{assignment.id}/status",
            json={"status": "COMPLETED"},
            headers=commander_headers,
        )
        assert res_invalid.status_code in (400, 422)

    def test_disasters_endpoints(self, client: TestClient, commander_headers: dict):
        # Create disaster via POST /api/v1/disasters
        payload = {
            "title": "API Created Disaster",
            "description": "Heavy emergency test",
            "disaster_type": "FIRE",
            "severity": "CRITICAL",
            "latitude": 30.7046,
            "longitude": 76.7985,
        }
        res_create = client.post("/api/v1/disasters", json=payload, headers=commander_headers)
        assert res_create.status_code == 201
        disaster_id = res_create.json()["data"]["id"]

        # GET /api/v1/disasters/{id}
        res_get = client.get(f"/api/v1/disasters/{disaster_id}", headers=commander_headers)
        assert res_get.status_code == 200
        assert res_get.json()["data"]["title"] == "API Created Disaster"

        # GET /api/v1/disasters/{id}/recommended-rescue-teams
        res_rec = client.get(
            f"/api/v1/disasters/{disaster_id}/recommended-rescue-teams", headers=commander_headers
        )
        assert res_rec.status_code == 200
        assert "recommended_team" in res_rec.json() or "teams" in res_rec.json()
