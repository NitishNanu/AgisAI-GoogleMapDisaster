"""
AegisAI Incident Module â€” API Router.

Endpoints:
  POST   /api/v1/incidents                              â€” Report incident
  GET    /api/v1/incidents                              â€” List incidents (filtered)
  GET    /api/v1/incidents/{id}                         â€” Get incident by ID
  PUT    /api/v1/incidents/{id}                         â€” Update incident
  DELETE /api/v1/incidents/{id}                         â€” Delete incident (ADMIN/COMMANDER)
  GET    /api/v1/incidents/{id}/nearest-rescue-team     â€” PostGIS nearest team
  GET    /api/v1/incidents/{id}/nearby-hospitals        â€” Hospitals within radius
  GET    /api/v1/incidents/{id}/nearby-shelters         â€” Shelters within radius
  GET    /api/v1/incidents/{id}/recommended-teams       â€” AI-ranked team recommendations
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.common.response import ApiResponse
from app.core.database.session import get_db
from app.core.security.jwt import RequireRole, get_current_active_user
from app.core.websocket.manager import ws_manager
from app.modules.auth.models import User
from app.modules.incident.schemas import (
    IncidentCreate,
    IncidentResponse,
    IncidentSummary,
    IncidentUpdate,
)
from app.modules.incident.service import IncidentService

router = APIRouter(prefix="/incidents", tags=["Incident Management"])


@router.post(
    "",
    response_model=ApiResponse[IncidentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Report a new emergency incident",
)
async def report_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ApiResponse[IncidentResponse]:
    """
    Report a new emergency incident at the specified coordinates.
    Any authenticated user may report an incident.
    """
    incident = IncidentService.report_incident(db, payload, reporter_id=current_user.id)
    response_data = IncidentResponse.model_validate(incident)

    # Broadcast to connected WebSocket clients
    try:
        await ws_manager.broadcast_to_channel(
            channel="incidents",
            event_type="INCIDENT_CREATED",
            data={
                "id": incident.id,
                "title": incident.title,
                "description": incident.description,
                "disaster_type": incident.disaster_type,
                "severity": incident.severity,
                "status": incident.status,
                "latitude": incident.latitude,
                "longitude": incident.longitude,
                "affected_radius_meters": incident.affected_radius_meters,
                "estimated_affected_people": incident.estimated_affected_people,
                "created_at": incident.created_at.isoformat() if incident.created_at else None,
            }
        )
    except Exception:
        pass

    return ApiResponse.created(
        data=response_data,
        message="Incident reported successfully.",
    )


@router.get(
    "",
    response_model=ApiResponse[dict],
    summary="List incidents with optional filters",
)
def list_incidents(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status"),
    type_filter: str | None = Query(default=None, alias="type", description="Filter by disaster type"),
    severity_filter: str | None = Query(default=None, alias="severity", description="Filter by severity"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """Return a paginated, filterable list of incidents."""
    incidents, total = IncidentService.list_incidents(
        db,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        type_filter=type_filter,
        severity_filter=severity_filter,
    )
    items = [IncidentSummary.model_validate(i) for i in incidents]
    return ApiResponse.paginated(
        data=[item.model_dump() for item in items],
        total=total,
        page=page,
        page_size=page_size,
        message=f"Retrieved {len(items)} incidents.",
    )


@router.get(
    "/{incident_id}",
    response_model=ApiResponse[IncidentResponse],
    summary="Get incident by ID",
)
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[IncidentResponse]:
    """Retrieve full details of a single incident."""
    incident = IncidentService.get_incident(db, incident_id)
    return ApiResponse.ok(
        data=IncidentResponse.model_validate(incident),
        message="Incident retrieved successfully.",
    )


@router.put(
    "/{incident_id}",
    response_model=ApiResponse[IncidentResponse],
    summary="Update an incident",
)
async def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[IncidentResponse]:
    """
    Update incident details (status, severity, coordinates, etc.).
    Requires DISPATCHER, COMMANDER, or ADMIN role.
    """
    incident = IncidentService.update_incident(
        db,
        incident_id,
        payload,
        current_user_id=current_user.id,
        current_user_role=current_user.role,
    )
    response_data = IncidentResponse.model_validate(incident)

    try:
        await ws_manager.broadcast_to_channel(
            channel="incidents",
            event_type="INCIDENT_UPDATED",
            data={
                "id": incident.id,
                "title": incident.title,
                "description": incident.description,
                "disaster_type": incident.disaster_type,
                "severity": incident.severity,
                "status": incident.status,
                "latitude": incident.latitude,
                "longitude": incident.longitude,
                "affected_radius_meters": incident.affected_radius_meters,
                "estimated_affected_people": incident.estimated_affected_people,
                "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
            }
        )
    except Exception:
        pass

    return ApiResponse.ok(
        data=response_data,
        message="Incident updated successfully.",
    )


@router.delete(
    "/{incident_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an incident (ADMIN/COMMANDER only)",
)
def delete_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER"])),
) -> None:
    """Hard-delete an incident. Use status updates instead for audit trails."""
    IncidentService.delete_incident(
        db, incident_id, current_user_role=current_user.role
    )
    return None


@router.get(
    "/{incident_id}/nearest-rescue-team",
    response_model=ApiResponse[dict | None],
    summary="Find the nearest available rescue team",
)
def nearest_rescue_team(
    incident_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[dict | None]:
    """
    Return the single nearest available rescue team using PostGIS ST_Distance.
    Returns null data if no teams are available.
    """
    result = IncidentService.get_nearest_rescue_team(db, incident_id)
    if result is None:
        return ApiResponse.ok(data=None, message="No available rescue teams found.")
    return ApiResponse.ok(data=result, message="Nearest rescue team found.")


@router.get(
    "/{incident_id}/nearby-hospitals",
    response_model=ApiResponse[dict],
    summary="Find hospitals within radius",
)
def nearby_hospitals(
    incident_id: int,
    radius_km: float = Query(default=10.0, gt=0, le=100, description="Search radius in km"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """Return all hospitals within the specified radius of the incident."""
    hospitals = IncidentService.get_nearby_hospitals(db, incident_id, radius_km)
    return ApiResponse.ok(
        data={"count": len(hospitals), "radius_km": radius_km, "hospitals": hospitals},
        message=f"Found {len(hospitals)} hospitals within {radius_km} km.",
    )


@router.get(
    "/{incident_id}/nearby-shelters",
    response_model=ApiResponse[dict],
    summary="Find shelters within radius",
)
def nearby_shelters(
    incident_id: int,
    radius_km: float = Query(default=10.0, gt=0, le=100, description="Search radius in km"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """Return all shelters with available space within the specified radius."""
    shelters = IncidentService.get_nearby_shelters(db, incident_id, radius_km)
    return ApiResponse.ok(
        data={"count": len(shelters), "radius_km": radius_km, "shelters": shelters},
        message=f"Found {len(shelters)} shelters within {radius_km} km.",
    )


@router.get(
    "/{incident_id}/recommended-teams",
    response_model=ApiResponse[dict],
    summary="Get AI-ranked rescue team recommendations",
)
async def recommended_teams(
    incident_id: int,
    limit: int = Query(default=5, ge=1, le=20, description="Number of teams to rank"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """
    Return ranked rescue team recommendations using OSRM routing and scoring.
    Teams are scored by ETA, vehicle type suitability, and team size.
    """
    teams = await IncidentService.get_recommended_teams(db, incident_id, limit=limit)
    return ApiResponse.ok(
        data={
            "incident_id": incident_id,
            "count": len(teams),
            "recommended": teams[0] if teams else None,
            "all_teams": teams,
        },
        message=f"Ranked {len(teams)} rescue teams.",
    )


@router.post(
    "/auto-discover",
    response_model=ApiResponse[dict],
    summary="Auto-detect disaster and discover nearby shelters & rescue teams",
    description="Takes raw unstructured text, automatically extracts disaster type, geocodes coordinates, and auto-discovers optimal rescue teams, shelters, and hospitals.",
)
async def auto_discover_incident(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ApiResponse[dict]:
    text = payload.get("text", "")
    persist = bool(payload.get("persist", False))

    result = await IncidentService.auto_discover_from_text(
        db=db,
        text=text,
        reporter_id=current_user.id,
        persist=persist,
    )

    # Broadcast to WebSocket if persisted
    if persist and result.get("detected_disaster", {}).get("incident_id"):
        try:
            inc_info = result["detected_disaster"]
            await ws_manager.broadcast_to_channel(
                channel="incidents",
                event_type="INCIDENT_CREATED",
                data={
                    "id": inc_info["incident_id"],
                    "title": f"Auto-Detected: {inc_info['disaster_type']}",
                    "disaster_type": inc_info["disaster_type"],
                    "severity": inc_info["severity"],
                    "latitude": inc_info["latitude"],
                    "longitude": inc_info["longitude"],
                    "status": "REPORTED",
                }
            )
        except Exception:
            pass

    return ApiResponse.ok(
        data=result,
        message="Disaster, shelters, and rescue teams auto-discovered successfully.",
    )


