"""
RescueNet AI — Assignments API Router.

Provides dispatching and mission lifecycle management endpoints:
  GET  /api/v1/assignments              — List assignments
  GET  /api/v1/assignments/{id}         — Get assignment
  POST /api/v1/assignments              — Dispatch team (transaction-safe)
  PUT  /api/v1/assignments/{id}/status  — Update mission status
  PUT  /api/v1/assignments/{id}         — General assignment update
"""

import json

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.core.cache.redis_client import get_redis
from app.core.common.response import ApiResponse
from app.core.common.sanitizer import sanitize_text
from app.core.database.session import get_db
from app.core.events.rabbitmq import publish_event
from app.core.security.jwt import RequireRole, get_current_active_user
from app.core.websocket.manager import ws_manager
from app.modules.auth.models import User
from app.modules.resource.models import ResourceAssignment
from app.modules.resource.schemas import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentStatusUpdate,
    AssignmentUpdate,
)
from app.services.assignment_service import AssignmentService

_idempotency_cache: dict[str, dict] = {}

router = APIRouter(prefix="/assignments", tags=["Assignments & Dispatch"])


@router.get(
    "",
    response_model=ApiResponse[dict],
    summary="List resource assignments",
)
def list_assignments(
    incident_id: int | None = Query(None, alias="disaster_id", description="Filter by incident/disaster ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> ApiResponse[dict]:
    query = db.query(ResourceAssignment)
    if incident_id is not None:
        query = query.filter(ResourceAssignment.incident_id == incident_id)

    total = query.count()
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


@router.get(
    "/{assignment_id}",
    response_model=ApiResponse[AssignmentResponse],
    summary="Get assignment by ID",
)
def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> ApiResponse[AssignmentResponse]:
    assignment = AssignmentService.get_assignment(db, assignment_id)
    return ApiResponse.ok(data=AssignmentResponse.model_validate(assignment))


@router.post(
    "",
    response_model=ApiResponse[AssignmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Dispatch a rescue team (transaction safe)",
)
async def dispatch_team(
    payload: AssignmentCreate,
    x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[AssignmentResponse]:
    # Check idempotency key if provided
    if x_idempotency_key:
        cache_key = f"aegis:idempotency:{x_idempotency_key}"
        r = get_redis()
        cached_bytes = None
        if r:
            try:
                cached_bytes = r.get(cache_key)
            except Exception:
                pass
        if cached_bytes:
            return ApiResponse.ok(
                data=AssignmentResponse(**json.loads(cached_bytes)),
                message="Returning previously dispatched assignment (idempotent duplicate).",
            )
        elif x_idempotency_key in _idempotency_cache:
            return ApiResponse.ok(
                data=AssignmentResponse(**_idempotency_cache[x_idempotency_key]),
                message="Returning previously dispatched assignment (idempotent duplicate).",
            )

    clean_notes = sanitize_text(payload.notes)
    assignment = AssignmentService.create_assignment(
        db=db,
        incident_id=payload.incident_id,
        team_id=payload.team_id,
        dispatched_by=current_user.id,
        notes=clean_notes,
        estimated_arrival_minutes=payload.estimated_arrival_minutes,
        distance_km=payload.distance_km,
        route_geometry=payload.route_geometry,
    )
    response_data = AssignmentResponse.model_validate(assignment)
    payload_dump = response_data.model_dump(mode="json")

    # Store in idempotency cache
    if x_idempotency_key:
        cache_key = f"aegis:idempotency:{x_idempotency_key}"
        _idempotency_cache[x_idempotency_key] = payload_dump
        if r := get_redis():
            try:
                r.set(cache_key, json.dumps(payload_dump), ex=300)
            except Exception:
                pass

    try:
        await ws_manager.broadcast_to_channel(
            channel="missions",
            event_type="MISSION_CREATED",
            data=payload_dump
        )
    except Exception:
        pass

    try:
        await publish_event("aegis.dispatch.created", payload_dump)
    except Exception:
        pass

    return ApiResponse.created(
        data=response_data,
        message="Rescue team dispatched successfully.",
    )


@router.put(
    "/{assignment_id}/status",
    response_model=ApiResponse[AssignmentResponse],
    summary="Update assignment status (Mission lifecycle transition)",
)
async def update_assignment_status(
    assignment_id: int,
    payload: AssignmentStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER", "RESPONDER"])),
) -> ApiResponse[AssignmentResponse]:
    assignment = AssignmentService.update_assignment_status(
        db=db,
        assignment_id=assignment_id,
        new_status=payload.status.value if hasattr(payload.status, "value") else str(payload.status),
    )
    response_data = AssignmentResponse.model_validate(assignment)

    try:
        await ws_manager.broadcast_to_channel(
            channel="missions",
            event_type="MISSION_UPDATED",
            data={
                "assignment_id": assignment.id,
                "status": assignment.status,
                "team_id": assignment.team_id,
                "incident_id": assignment.incident_id,
                "started_at": assignment.started_at.isoformat() if assignment.started_at else None,
                "completed_at": assignment.completed_at.isoformat() if assignment.completed_at else None,
            }
        )
    except Exception:
        pass

    return ApiResponse.ok(
        data=response_data,
        message=f"Mission assignment status updated to {assignment.status}.",
    )


@router.put(
    "/{assignment_id}",
    response_model=ApiResponse[AssignmentResponse],
    summary="Update assignment details",
)
def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER", "RESPONDER"])),
) -> ApiResponse[AssignmentResponse]:
    target_status = payload.status.value if payload.status and hasattr(payload.status, "value") else (str(payload.status) if payload.status else None)

    if target_status:
        assignment = AssignmentService.update_assignment_status(
            db=db,
            assignment_id=assignment_id,
            new_status=target_status,
            notes=payload.notes,
        )
    else:
        assignment = AssignmentService.get_assignment(db, assignment_id)
        if payload.notes is not None:
            assignment.notes = payload.notes
        if payload.estimated_arrival_minutes is not None:
            assignment.estimated_arrival_minutes = payload.estimated_arrival_minutes
        if payload.distance_km is not None:
            assignment.distance_km = payload.distance_km
        db.commit()
        db.refresh(assignment)

    return ApiResponse.ok(
        data=AssignmentResponse.model_validate(assignment),
        message="Assignment updated successfully.",
    )
