"""
RescueNet AI — Missions API Router.

Provides Mission Control viewing and real-time tracking endpoints:
  GET /api/v1/missions — List all missions / active missions
"""

from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.common.response import ApiResponse
from app.core.database.session import get_db
from app.services.mission_service import MissionService

router = APIRouter(prefix="/missions", tags=["Mission Control"])


@router.get(
    "",
    summary="Get mission tracking data for Mission Control",
)
def get_missions(
    active_only: bool = Query(default=False, description="Filter only active missions"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return comprehensive nested mission information for dashboard visualization:
    - assignment_id, status
    - disaster (id, title, type, severity, status, coordinates)
    - team (id, name, vehicle_type, members, status, coordinates)
    - distance_km, eta_minutes, route_geometry
    - started_at, completed_at, created_at
    """
    missions = MissionService.get_active_missions(db, active_only=active_only)
    return {
        "success": True,
        "count": len(missions),
        "data": missions,
    }

from app.modules.ai.providers.ollama_provider import ollama_provider
from fastapi import HTTPException
from sqlalchemy import text

@router.post("/{assignment_id}/sitrep")
async def generate_sitrep(assignment_id: str, db: Session = Depends(get_db)):
    # Mock mission data retrieval
    mission = MissionService.get_mission_by_id(db, assignment_id)
    if not mission:
        # Fallback for demo
        mission = {
            "assignment_id": assignment_id,
            "status": "EN_ROUTE",
            "team_name": "Rescue Alpha",
            "vehicle_type": "AMBULANCE",
            "incident_title": "Multi-Vehicle Collision",
            "distance_remaining_km": 4.2,
            "elapsed_minutes": 12.5,
        }
    
    elapsed_val = float(mission.get("elapsed_minutes") or 10.0)

    # AI SITREP Call
    decision_data = {
        "action": {
            "resource_name": mission.get("team_name"),
            "vehicle_type": mission.get("vehicle_type"),
            "incident_id": mission.get("assignment_id"),
            "distance_km": mission.get("distance_remaining_km"),
            "estimated_arrival_minutes": elapsed_val + 5.0,
        },
        "reasoning": ["Fastest unit available", "Has required medical capacity"],
        "expected_impact": {"casualties_treated": 2},
        "alternatives": []
    }
    
    briefing = await ollama_provider.generate_briefing(decision_data)
    
    return {
        "success": True,
        "incident_title": mission.get("incident_title"),
        "team_name": mission.get("team_name"),
        "vehicle_type": mission.get("vehicle_type"),
        "distance_remaining_km": mission.get("distance_remaining_km"),
        "elapsed_minutes": mission.get("elapsed_minutes"),
        "tactical_next_steps": briefing.recommended_next_steps,
        "anomalies": [
            {"anomaly_type": "Traffic", "severity": "HIGH", "description": "Congestion on Route 9", "recommended_action": "Reroute"}
        ] if briefing.operational_risks else [],
        "operational_milestones": briefing.reasons,
        "backup_recommended": True,
        "recommended_backup_type": "FIRE TRUCK"
    }

@router.post("/{assignment_id}/medevac")
def get_medevac_plan(assignment_id: str, db: Session = Depends(get_db)):
    # Execute PostGIS query to find the nearest hospital with available ICU beds within 50km
    query = text("""
        SELECT 
            id, 
            name, 
            trauma_level, 
            available_beds, 
            available_icu_beds as icu_beds_available,
            ST_Distance(
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 
                location::geography
            ) / 1000.0 as distance_km
        FROM hospitals
        WHERE is_operational = true 
          AND available_icu_beds > 0
          AND ST_DWithin(
              ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 
              location::geography, 
              50000
          )
        ORDER BY distance_km ASC
        LIMIT 3
    """)
    
    # Mock incident coordinates for routing
    incident_lon, incident_lat = 76.7794, 30.7333 
    
    result = db.execute(query, {"lon": incident_lon, "lat": incident_lat}).fetchall()
    
    if not result:
        return {"success": False, "message": "No hospitals with ICU beds found within 50km."}
    
    # OSRM Route ETA calculation (simulated here)
    hospitals = []
    for r in result:
        hospitals.append({
            "hospital_id": r.id,
            "hospital_name": r.name,
            "trauma_level": r.trauma_level,
            "available_beds": r.available_beds,
            "icu_beds_available": r.icu_beds_available,
            "distance_km": round(r.distance_km, 2),
            "eta_minutes": round((r.distance_km / 50.0) * 60, 1) # assuming 50km/h avg speed
        })
        
    primary = hospitals[0]
    alternatives = hospitals[1:]

    # Notify via WebSocket about the Medevac route
    try:
        from app.core.websocket.manager import ws_manager
        import asyncio
        asyncio.create_task(
            ws_manager.broadcast_to_channel("missions", "MEDEVAC_ROUTED", {
                "assignment_id": assignment_id,
                "hospital_id": primary["hospital_id"],
                "distance_km": primary["distance_km"],
                "eta_minutes": primary["eta_minutes"]
            })
        )
    except Exception:
        pass

    return {
        "success": True,
        "assignment_id": assignment_id,
        "triage_notes": "Multiple critical trauma victims. Immediate ICU care required.",
        "critical_patients_count": 2,
        "selected_hospital": primary,
        "alternative_hospitals": alternatives
    }
