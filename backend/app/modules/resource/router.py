"""
AegisAI Resource Module â€” API Router.

Endpoints for managing Rescue Teams, Shelters, and Assignments.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.common.response import ApiResponse
from app.core.database.session import get_db
from app.core.security.jwt import RequireRole
from app.modules.auth.models import User
from app.modules.resource.schemas import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentUpdate,
    RescueTeamCreate,
    RescueTeamResponse,
    RescueTeamUpdate,
    ShelterCreate,
    ShelterResponse,
    ShelterUpdate,
)
from app.modules.resource.service import ResourceService

router = APIRouter(prefix="/resources", tags=["Resource Management"])

# ---------------------------------------------------------------------------
# Rescue Teams
# ---------------------------------------------------------------------------
@router.post(
    "/teams",
    response_model=ApiResponse[RescueTeamResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new rescue team (ADMIN/COMMANDER)",
)
def create_team(
    payload: RescueTeamCreate,
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER"])),
) -> ApiResponse[RescueTeamResponse]:
    team = ResourceService.create_team(db, payload)
    return ApiResponse.created(data=RescueTeamResponse.model_validate(team))


@router.get(
    "/teams",
    response_model=ApiResponse[dict],
    summary="List all rescue teams",
)
def list_teams(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    teams, total = ResourceService.list_teams(db, page, page_size, status_filter)
    items = [RescueTeamResponse.model_validate(t).model_dump() for t in teams]
    return ApiResponse.paginated(data=items, total=total, page=page, page_size=page_size)


@router.get(
    "/teams/{team_id}",
    response_model=ApiResponse[RescueTeamResponse],
)
def get_team(
    team_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[RescueTeamResponse]:
    team = ResourceService.get_team(db, team_id)
    return ApiResponse.ok(data=RescueTeamResponse.model_validate(team))


@router.put(
    "/teams/{team_id}",
    response_model=ApiResponse[RescueTeamResponse],
    summary="Update a rescue team (ADMIN/COMMANDER/DISPATCHER)",
)
def update_team(
    team_id: int,
    payload: RescueTeamUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[RescueTeamResponse]:
    team = ResourceService.update_team(db, team_id, payload)
    return ApiResponse.ok(data=RescueTeamResponse.model_validate(team))


@router.delete(
    "/teams/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a rescue team (ADMIN)",
)
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN"])),
) -> None:
    ResourceService.delete_team(db, team_id)
    return None


# ---------------------------------------------------------------------------
# Shelters
# ---------------------------------------------------------------------------
@router.post(
    "/shelters",
    response_model=ApiResponse[ShelterResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new shelter (ADMIN/COMMANDER)",
)
def create_shelter(
    payload: ShelterCreate,
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER"])),
) -> ApiResponse[ShelterResponse]:
    shelter = ResourceService.create_shelter(db, payload)
    return ApiResponse.created(data=ShelterResponse.model_validate(shelter))


@router.get(
    "/shelters",
    response_model=ApiResponse[dict],
    summary="List all shelters",
)
def list_shelters(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    available_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    shelters, total = ResourceService.list_shelters(db, page, page_size, available_only)
    items = [ShelterResponse.model_validate(s).model_dump() for s in shelters]
    return ApiResponse.paginated(data=items, total=total, page=page, page_size=page_size)


@router.get("/shelters/{shelter_id}", response_model=ApiResponse[ShelterResponse])
def get_shelter(
    shelter_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse[ShelterResponse]:
    shelter = ResourceService.get_shelter(db, shelter_id)
    return ApiResponse.ok(data=ShelterResponse.model_validate(shelter))


@router.put("/shelters/{shelter_id}", response_model=ApiResponse[ShelterResponse])
def update_shelter(
    shelter_id: int,
    payload: ShelterUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER"])),
) -> ApiResponse[ShelterResponse]:
    shelter = ResourceService.update_shelter(db, shelter_id, payload)
    return ApiResponse.ok(data=ShelterResponse.model_validate(shelter))


@router.delete("/shelters/{shelter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shelter(
    shelter_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN"])),
) -> None:
    ResourceService.delete_shelter(db, shelter_id)
    return None


# ---------------------------------------------------------------------------
# Assignments (Dispatching)
# ---------------------------------------------------------------------------
@router.get(
    "/assignments",
    response_model=ApiResponse[dict],
    summary="List resource assignments (optionally filtered by incident)",
)
def list_assignments(
    incident_id: int | None = Query(None, description="Filter assignments by incident ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """
    Return a paginated list of resource assignments.

    Optionally filter to a specific incident by providing `incident_id`.
    Without a filter, returns the most recent assignments across all incidents.
    """
    from app.modules.resource.models import ResourceAssignment  # noqa: PLC0415

    query = db.query(ResourceAssignment)
    if incident_id is not None:
        query = query.filter(ResourceAssignment.incident_id == incident_id)

    total: int = query.count()
    skip = (page - 1) * page_size
    assignments = (
        query.order_by(ResourceAssignment.created_at.desc())
        .offset(skip)
        .limit(page_size)
        .all()
    )

    items = [AssignmentResponse.model_validate(a).model_dump() for a in assignments]
    return ApiResponse.paginated(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
        message=f"Retrieved {len(items)} assignments.",
    )



@router.post(
    "/assignments",
    response_model=ApiResponse[AssignmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Dispatch a team to an incident",
)
def dispatch_team(
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[AssignmentResponse]:
    assignment = ResourceService.dispatch_team(db, payload, dispatcher_id=current_user.id)
    return ApiResponse.created(data=AssignmentResponse.model_validate(assignment))


@router.put(
    "/assignments/{assignment_id}",
    response_model=ApiResponse[AssignmentResponse],
    summary="Update assignment status",
)
def update_assignment_status(
    assignment_id: int,
    payload: AssignmentUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER", "RESPONDER"])),
) -> ApiResponse[AssignmentResponse]:
    assignment = ResourceService.update_assignment_status(db, assignment_id, payload)
    return ApiResponse.ok(data=AssignmentResponse.model_validate(assignment))
