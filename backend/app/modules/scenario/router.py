"""
AegisAI Scenario Module — REST API Router.
Provides endpoints for scenario configuration, validation, baseline risk previews, cloning, and simulation execution.
Python 3.10 compatible.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.common.response import ApiResponse
from app.core.database.session import get_db
from app.core.security.jwt import RequireRole, get_optional_user
from app.modules.auth.models import User
from app.modules.scenario.schemas import (
    PresetResponse,
    ScenarioCloneRequest,
    ScenarioCreateRequest,
    ScenarioPreviewResponse,
    ScenarioResponse,
    ScenarioRunResponse,
    ScenarioUpdateRequest,
    ScenarioValidateResponse,
)
from app.modules.scenario.service import ScenarioService

router = APIRouter(prefix="/scenarios", tags=["Scenario Management & Designer"])


# --- Presets, Validation & Preview Endpoints ---------------------------------

@router.get(
    "/presets",
    response_model=ApiResponse[list[PresetResponse]],
    summary="Get standardized disaster scenario presets",
)
def get_scenario_presets() -> ApiResponse[list[PresetResponse]]:
    """Return catalog of standardized, ready-to-run disaster scenario blueprints."""
    presets = ScenarioService.get_presets()
    return ApiResponse.ok(data=presets, message=f"Retrieved {len(presets)} scenario presets.")


@router.post(
    "/validate",
    response_model=ApiResponse[ScenarioValidateResponse],
    summary="Validate scenario configuration parameters",
)
def validate_scenario(
    payload: ScenarioCreateRequest,
    _: User | None = Depends(get_optional_user),
) -> ApiResponse[ScenarioValidateResponse]:
    """Validate a scenario configuration payload without saving it to database."""
    res = ScenarioService.validate_scenario(payload)
    return ApiResponse.ok(data=res, message=res.message)


@router.post(
    "/preview",
    response_model=ApiResponse[ScenarioPreviewResponse],
    summary="Generate baseline impact and risk preview",
)
def preview_scenario(
    payload: ScenarioCreateRequest,
    _: User | None = Depends(get_optional_user),
) -> ApiResponse[ScenarioPreviewResponse]:
    """
    Compute estimated casualty ranges, hospital/shelter demand, and baseline risk score
    for a scenario configuration prior to launch.
    """
    preview = ScenarioService.preview_scenario(payload)
    return ApiResponse.ok(data=preview, message="Scenario impact preview calculated.")


# --- Scenario CRUD Endpoints -------------------------------------------------

@router.post(
    "",
    response_model=ApiResponse[ScenarioResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new scenario blueprint (COMMANDER+)",
)
def create_scenario(
    payload: ScenarioCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[ScenarioResponse]:
    """Persist a new disaster scenario blueprint."""
    scenario = ScenarioService.create_scenario(db, payload, user_id=current_user.id)
    return ApiResponse.created(
        data=ScenarioResponse.model_validate(scenario),
        message=f"Scenario '{scenario.name}' created successfully.",
    )


@router.get(
    "",
    response_model=ApiResponse[dict[str, Any]],
    summary="List scenarios with filtering and search",
)
def list_scenarios(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="Filter by status: READY | RUNNING | DRAFT"),
    disaster_type: str | None = Query(default=None, description="Filter by disaster type"),
    severity: str | None = Query(default=None, description="Filter by severity"),
    is_template: bool | None = Query(default=None, description="Filter templates only"),
    search: str | None = Query(default=None, description="Search keyword in title/desc"),
    db: Session = Depends(get_db),
    _: User | None = Depends(get_optional_user),
) -> ApiResponse[dict[str, Any]]:
    """Retrieve paginated scenarios with search and filter options."""
    skip = (page - 1) * page_size
    scenarios, total = ScenarioService.get_scenarios(
        db,
        skip=skip,
        limit=page_size,
        status=status,
        disaster_type=disaster_type,
        severity=severity,
        is_template=is_template,
        search=search,
    )
    items = [ScenarioResponse.model_validate(s).model_dump() for s in scenarios]
    return ApiResponse.paginated(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
        message=f"Retrieved {len(items)} scenarios.",
    )


@router.get(
    "/{scenario_id}",
    response_model=ApiResponse[ScenarioResponse],
    summary="Get scenario configuration details",
)
def get_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
    _: User | None = Depends(get_optional_user),
) -> ApiResponse[ScenarioResponse]:
    """Retrieve complete scenario configuration by ID."""
    scenario = ScenarioService.get_scenario(db, scenario_id)
    return ApiResponse.ok(data=ScenarioResponse.model_validate(scenario), message="Scenario retrieved.")


@router.patch(
    "/{scenario_id}",
    response_model=ApiResponse[ScenarioResponse],
    summary="Update scenario configuration (COMMANDER+)",
)
def update_scenario(
    scenario_id: str,
    payload: ScenarioUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[ScenarioResponse]:
    """Update editable scenario details."""
    scenario = ScenarioService.update_scenario(db, scenario_id, payload, user_id=current_user.id)
    return ApiResponse.ok(
        data=ScenarioResponse.model_validate(scenario),
        message=f"Scenario '{scenario.name}' updated successfully.",
    )


@router.delete(
    "/{scenario_id}",
    response_model=ApiResponse[None],
    summary="Archive scenario (COMMANDER+)",
)
def archive_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER"])),
) -> ApiResponse[None]:
    """Soft-delete/archive a disaster scenario."""
    ScenarioService.archive_scenario(db, scenario_id, user_id=current_user.id)
    return ApiResponse.ok(data=None, message=f"Scenario '{scenario_id}' archived successfully.")


# --- Execution, Cloning & Replay Endpoints -----------------------------------

@router.post(
    "/{scenario_id}/clone",
    response_model=ApiResponse[ScenarioResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Clone scenario for What-If comparative analysis (COMMANDER+)",
)
def clone_scenario(
    scenario_id: str,
    payload: ScenarioCloneRequest = ScenarioCloneRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[ScenarioResponse]:
    """Clone an existing scenario with a new UUID for parameter branching and What-If analysis."""
    cloned = ScenarioService.clone_scenario(
        db,
        scenario_id,
        new_name=payload.new_name,
        user_id=current_user.id,
    )
    return ApiResponse.created(
        data=ScenarioResponse.model_validate(cloned),
        message=f"Cloned scenario created: '{cloned.name}'.",
    )


@router.post(
    "/{scenario_id}/launch",
    response_model=ApiResponse[ScenarioRunResponse],
    summary="Launch scenario simulation in Digital Twin (COMMANDER+)",
)
async def launch_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[ScenarioRunResponse]:
    """
    Launch scenario in the authoritative Digital Twin simulation engine.
    Initializes simulation clock, injects disaster hazard, sets environmental conditions,
    and broadcasts real-time launch event.
    """
    run = await ScenarioService.launch_scenario(db, scenario_id, user_id=current_user.id)
    return ApiResponse.ok(
        data=ScenarioRunResponse.model_validate(run),
        message=f"Scenario launched! Simulation run ID: {run.id}",
    )


@router.get(
    "/{scenario_id}/runs",
    response_model=ApiResponse[list[ScenarioRunResponse]],
    summary="Get execution history for a scenario",
)
def get_scenario_runs(
    scenario_id: str,
    db: Session = Depends(get_db),
    _: User | None = Depends(get_optional_user),
) -> ApiResponse[list[ScenarioRunResponse]]:
    """Retrieve historical execution runs for a scenario."""
    runs = ScenarioService.get_scenario_runs(db, scenario_id)
    return ApiResponse.ok(
        data=[ScenarioRunResponse.model_validate(r) for r in runs],
        message=f"Retrieved {len(runs)} simulation runs.",
    )


@router.get(
    "/{scenario_id}/snapshot",
    response_model=ApiResponse[dict[str, Any]],
    summary="Get initial snapshot recorded at scenario launch",
)
def get_scenario_snapshot(
    scenario_id: str,
    db: Session = Depends(get_db),
    _: User | None = Depends(get_optional_user),
) -> ApiResponse[dict[str, Any]]:
    """Get the initial digital twin snapshot recorded for the latest run of this scenario."""
    runs = ScenarioService.get_scenario_runs(db, scenario_id)
    if not runs or not runs[0].initial_state_snapshot:
        return ApiResponse.ok(data={}, message="No initial snapshot found for this scenario.")
    return ApiResponse.ok(data=runs[0].initial_state_snapshot, message="Initial state snapshot retrieved.")
