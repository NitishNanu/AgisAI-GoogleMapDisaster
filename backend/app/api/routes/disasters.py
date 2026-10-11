"""
RescueNet AI — Disasters API Router.

Provides disaster management endpoints matching the Master Development Prompt:
  GET    /api/v1/disasters                                      — List disasters
  GET    /api/v1/disasters/{id}                                 — Get disaster by ID
  POST   /api/v1/disasters                                      — Report disaster
  PUT    /api/v1/disasters/{id}                                 — Update disaster
  DELETE /api/v1/disasters/{id}                                 — Delete disaster
  GET    /api/v1/disasters/{id}/nearest-rescue-team             — PostGIS nearest team
  GET    /api/v1/disasters/{id}/route-to-rescue-team/{team_id}   — OSRM route to team
  GET    /api/v1/disasters/{id}/recommended-rescue-teams        — Smart-ranked teams
  GET    /api/v1/disasters/{id}/nearby-hospitals                — Nearby hospitals
  GET    /api/v1/disasters/{id}/nearby-shelters                 — Nearby shelters
"""

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.common.exceptions import EntityNotFoundException
from app.core.common.response import ApiResponse
from app.core.database.session import get_db
from app.core.security.jwt import RequireRole, get_current_active_user
from app.modules.auth.models import User
from app.modules.incident.models import Incident
from app.modules.incident.schemas import (
    IncidentCreate as DisasterCreate,
)
from app.modules.incident.schemas import (
    IncidentResponse as DisasterResponse,
)
from app.modules.incident.schemas import (
    IncidentSummary as DisasterSummary,
)
from app.modules.incident.schemas import (
    IncidentUpdate as DisasterUpdate,
)
from app.modules.incident.service import IncidentService
from app.modules.resource.models import RescueTeam
from app.routing.osrm import OSRMService
from app.services.geospatial_service import GeospatialService
from app.services.smart_dispatch_service import SmartDispatchService

router = APIRouter(prefix="/disasters", tags=["Disaster Management"])


@router.post(
    "",
    response_model=ApiResponse[DisasterResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Report a new disaster",
)
def report_disaster(
    payload: DisasterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ApiResponse[DisasterResponse]:
    incident = IncidentService.report_incident(db, payload, reporter_id=current_user.id)
    return ApiResponse.created(
        data=DisasterResponse.model_validate(incident),
        message="Disaster reported successfully.",
    )


@router.get(
    "",
    response_model=ApiResponse[dict],
    summary="List all disasters",
)
def list_disasters(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(None, alias="status"),
    type_filter: str | None = Query(None, alias="type"),
    severity_filter: str | None = Query(None, alias="severity"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    incidents, total = IncidentService.list_incidents(
        db,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        type_filter=type_filter,
        severity_filter=severity_filter,
    )
    items = [DisasterSummary.model_validate(i).model_dump() for i in incidents]
    return ApiResponse.paginated(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
        message=f"Retrieved {len(items)} disasters.",
    )


@router.get(
    "/{disaster_id}",
    response_model=ApiResponse[DisasterResponse],
    summary="Get disaster details",
)
def get_disaster(
    disaster_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[DisasterResponse]:
    incident = IncidentService.get_incident(db, disaster_id)
    return ApiResponse.ok(data=DisasterResponse.model_validate(incident))


@router.put(
    "/{disaster_id}",
    response_model=ApiResponse[DisasterResponse],
    summary="Update a disaster",
)
def update_disaster(
    disaster_id: int,
    payload: DisasterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[DisasterResponse]:
    incident = IncidentService.update_incident(
        db,
        disaster_id,
        payload,
        current_user_id=current_user.id,
        current_user_role=current_user.role,
    )
    return ApiResponse.ok(data=DisasterResponse.model_validate(incident))


@router.delete(
    "/{disaster_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a disaster",
)
def delete_disaster(
    disaster_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER"])),
) -> None:
    IncidentService.delete_incident(db, disaster_id, current_user_role=current_user.role)
    return None


@router.get(
    "/{disaster_id}/nearest-rescue-team",
    response_model=ApiResponse[dict | None],
    summary="Find nearest available rescue team",
)
def get_nearest_team(
    disaster_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[dict | None]:
    result = GeospatialService.get_nearest_rescue_team(db, disaster_id)
    if result is None:
        return ApiResponse.ok(data=None, message="No available rescue teams found.")
    return ApiResponse.ok(data=result, message="Nearest rescue team found.")


@router.get(
    "/{disaster_id}/route-to-rescue-team/{team_id}",
    response_model=ApiResponse[dict],
    summary="Calculate OSRM route between disaster and rescue team",
)
async def route_to_rescue_team(
    disaster_id: int,
    team_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    incident = db.query(Incident).filter(Incident.id == disaster_id).first()
    if incident is None:
        raise EntityNotFoundException("Disaster", disaster_id)

    team = db.query(RescueTeam).filter(RescueTeam.id == team_id).first()
    if team is None:
        raise EntityNotFoundException("RescueTeam", team_id)

    # Route from team location to disaster location
    route = await OSRMService.get_route(
        start_lat=team.latitude,
        start_lon=team.longitude,
        end_lat=incident.latitude,
        end_lon=incident.longitude,
    )

    return ApiResponse.ok(
        data={
            "disaster_id": disaster_id,
            "rescue_team_id": team_id,
            "distance_km": route.get("distance_km"),
            "duration_minutes": route.get("duration_minutes"),
            "geometry": route.get("geometry"),
        },
        message="Route calculated successfully.",
    )


@router.get(
    "/{disaster_id}/recommended-rescue-teams",
    summary="Get smart-ranked rescue team recommendations",
)
async def recommended_rescue_teams(
    disaster_id: int,
    limit: int = Query(5, ge=1, le=20, description="Candidate limit (Top K)"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return await SmartDispatchService.get_dispatch_recommendation(
        db, disaster_id=disaster_id, limit=limit
    )


@router.get(
    "/{disaster_id}/nearby-hospitals",
    response_model=ApiResponse[dict],
    summary="Find hospitals near disaster",
)
def nearby_hospitals(
    disaster_id: int,
    radius_km: float = Query(10.0, gt=0, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    hospitals = IncidentService.get_nearby_hospitals(db, disaster_id, radius_km)
    return ApiResponse.ok(
        data={"count": len(hospitals), "radius_km": radius_km, "hospitals": hospitals},
        message=f"Found {len(hospitals)} hospitals within {radius_km} km.",
    )


@router.get(
    "/{disaster_id}/nearby-shelters",
    response_model=ApiResponse[dict],
    summary="Find shelters near disaster",
)
def nearby_shelters(
    disaster_id: int,
    radius_km: float = Query(10.0, gt=0, le=100),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    shelters = IncidentService.get_nearby_shelters(db, disaster_id, radius_km)
    return ApiResponse.ok(
        data={"count": len(shelters), "radius_km": radius_km, "shelters": shelters},
        message=f"Found {len(shelters)} shelters within {radius_km} km.",
    )

