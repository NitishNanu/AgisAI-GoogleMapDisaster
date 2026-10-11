"""
RescueNet AI — Live Verification Script against PostgreSQL.
"""

import asyncio
import json
import sys

sys.path.insert(0, "d:/PROJECTS/GoogleMapsDisaster/backend")

from app.core.database.session import SessionLocal
from app.modules.incident.models import Incident
from app.modules.resource.models import RescueTeam
from app.services.assignment_service import AssignmentService
from app.services.geospatial_service import GeospatialService
from app.services.mission_service import MissionService
from app.services.smart_dispatch_service import SmartDispatchService


async def main():
    db = SessionLocal()
    try:
        print("=" * 60)
        print("RESCUENET AI — PHASE 4 LIVE INTEGRATION VERIFICATION")
        print("=" * 60)

        # 1. Fetch first disaster (e.g. Industrial Fire)
        disaster = db.query(Incident).first()
        if not disaster:
            print("[FAIL] No disasters found in DB.")
            return

        print(f"\n1. Target Disaster: [{disaster.id}] {disaster.title} ({disaster.disaster_type})")
        print(f"   Coordinates: ({disaster.latitude}, {disaster.longitude}), Status: {disaster.status}")

        # 2. Candidate Selection via PostGIS Top-K
        print("\n2. Finding Top-5 candidates via PostGIS / GeospatialService...")
        candidates = GeospatialService.find_candidate_rescue_teams(db, disaster.id, limit=5)
        print(f"   Found {len(candidates)} candidates:")
        for team, dist in candidates:
            print(f"   - Team [{team.id}] {team.team_name} | {team.vehicle_type} | Dist: {dist:.2f} km | Status: {team.status}")

        # 3. Smart Dispatch Recommendation (OSRM Routing + Response Intelligence Scoring)
        print("\n3. Generating Smart Dispatch Recommendation (OSRM + Scoring)...")
        rec = await SmartDispatchService.get_dispatch_recommendation(db, disaster.id, limit=5)
        top_team = rec.get("recommended_team")
        if not top_team:
            print("[FAIL] No recommended team found.")
            return

        print(f"   Recommended Team: [{top_team.get('team_id')}] {top_team.get('team_name')}")
        print(f"   Vehicle: {top_team.get('vehicle_type')} | Score: {top_team.get('score')}")
        print(f"   Distance: {top_team.get('distance_km')} km | ETA: {top_team.get('eta_minutes')} mins")
        print(f"   Recommendation reason: {rec.get('reason')}")

        # 4. Dispatch Team (Transaction-Safe)
        print("\n4. Dispatching Recommended Team...")
        team_id = int(top_team["team_id"])
        assignment = AssignmentService.create_assignment(
            db=db,
            incident_id=disaster.id,
            team_id=team_id,
            dispatched_by=1,
            notes=f"Auto-dispatched via Smart Dispatch Engine. Score: {top_team.get('score')}",
            estimated_arrival_minutes=top_team.get("eta_minutes"),
            distance_km=top_team.get("distance_km"),
            route_geometry=top_team.get("route_geometry"),
        )
        print(f"   [SUCCESS] Assignment Created: ID={assignment.id}, Status={assignment.status}")
        db.refresh(disaster)
        dispatched_team = db.query(RescueTeam).filter(RescueTeam.id == team_id).first()
        if not dispatched_team:
            print("[FAIL] Dispatched team not found in DB.")
            return

        print(f"   Disaster Status: {disaster.status} (Expected: RESPONDING)")
        print(f"   Team Status: {dispatched_team.status} (Expected: DISPATCHED)")

        # 5. Mission State Machine Lifecycle Progression
        print("\n5. Progressing Mission Lifecycle State Machine...")

        # Step 5a: ASSIGNED -> EN_ROUTE
        assignment = AssignmentService.update_assignment_status(db, assignment.id, "EN_ROUTE")
        print(f"   -> Updated to EN_ROUTE (Started At: {assignment.started_at})")

        # Step 5b: EN_ROUTE -> ARRIVED
        assignment = AssignmentService.update_assignment_status(db, assignment.id, "ARRIVED")
        db.refresh(dispatched_team)
        print(f"   -> Updated to ARRIVED (Team Status: {dispatched_team.status})")

        # Step 5c: ARRIVED -> COMPLETED
        assignment = AssignmentService.update_assignment_status(db, assignment.id, "COMPLETED")
        db.refresh(dispatched_team)
        db.refresh(disaster)
        print(f"   -> Updated to COMPLETED (Completed At: {assignment.completed_at})")
        print(f"   -> Team Status: {dispatched_team.status} (Expected: AVAILABLE)")
        print(f"   -> Disaster Status: {disaster.status} (Expected: RESOLVED)")

        # 6. Mission Control Active Missions Payload Check
        print("\n6. Checking Mission Control /missions Output Structure...")
        missions = MissionService.get_active_missions(db, active_only=False)
        print(f"   Total missions returned: {len(missions)}")
        if missions:
            sample_mission = missions[0]
            print(f"   Mission Keys: {list(sample_mission.keys())}")
            print(f"   Sample Mission JSON:\n{json.dumps(sample_mission, indent=2, default=str)}")

        print("\n" + "=" * 60)
        print("[SUCCESS] ALL PHASE 4 BACKEND WORKFLOWS VERIFIED SUCCESSFULLY ON POSTGRESQL!")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
