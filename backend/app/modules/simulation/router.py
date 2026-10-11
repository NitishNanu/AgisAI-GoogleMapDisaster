"""
AegisAI Simulation Module — API Router.

Provides endpoints to control the Digital Twin Engine and query its state.

Control endpoints (ADMIN only):
  POST /api/v1/simulation/action         — start | stop | tick | reset
  PUT  /api/v1/simulation/config         — update engine runtime config
  POST /api/v1/simulation/spawn-incident — inject incident into twin

Query endpoints (authenticated):
  GET  /api/v1/simulation/state          — engine status + metadata
  GET  /api/v1/simulation/snapshot       — full city state (tick snapshot)
  GET  /api/v1/simulation/events         — recent event log
  GET  /api/v1/simulation/citizens       — paginated citizen agent states
  GET  /api/v1/simulation/buildings      — building states with damage tracking
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.common.response import ApiResponse
from app.core.database.session import get_db
from app.core.security.jwt import RequireRole, get_optional_user
from app.modules.auth.models import User
from app.modules.simulation.schemas import (
    BuildingState,
    DigitalTwinCityState,
    SimulationActionRequest,
    SimulationConfig,
    SimulationEvent,
    SimulationStateResponse,
    SpawnIncidentRequest,
)
from app.modules.simulation.service import SimulationService

router = APIRouter(prefix="/simulation", tags=["Digital Twin Simulation"])


# --- Engine Control (ADMIN only) --------------------------------------------

@router.post(
    "/action",
    response_model=ApiResponse[SimulationStateResponse],
    summary="Execute simulation engine action (ADMIN/COMMANDER/DISPATCHER)",
)
async def perform_simulation_action(
    payload: SimulationActionRequest,
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[SimulationStateResponse]:
    """
    Control the Digital Twin Engine.

    Supported actions:
      - `start`: Begin automatic tick processing via the scheduler
      - `stop` / `pause`: Halt automatic tick processing
      - `resume`: Resume tick processing
      - `tick`: Manually process exactly one tick immediately
      - `reset`: Full engine reset (destroys all current state!)
    """
    state = await SimulationService.perform_action(payload)
    return ApiResponse.ok(
        data=state,
        message=f"Action '{payload.action}' executed successfully.",
    )


@router.put(
    "/config",
    response_model=ApiResponse[SimulationStateResponse],
    summary="Update simulation engine configuration (ADMIN/COMMANDER)",
)
def update_simulation_config(
    payload: SimulationConfig,
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER"])),
) -> ApiResponse[SimulationStateResponse]:
    """
    Update global simulation parameters at runtime without a restart.

    Configurable parameters:
      - `weather_multiplier`: Amplifies weather severity effects
      - `traffic_multiplier`: Amplifies road congestion effects
      - `citizen_panic_factor`: Controls how quickly citizens become endangered
      - `auto_spawn_incidents`: Enable autonomous random incident generation
    """
    state = SimulationService.update_config(payload)
    return ApiResponse.ok(data=state, message="Simulation configuration updated.")


@router.post(
    "/spawn-incident",
    response_model=ApiResponse[dict],
    summary="Inject an incident directly into the digital twin (ADMIN/COMMANDER/DISPATCHER)",
)
def spawn_incident(
    payload: SpawnIncidentRequest,
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[dict]:
    """
    Force-spawn an incident at the given coordinates in the simulation.

    Immediately registers the incident in the engine's disaster proximity
    tracker, affecting citizen state transitions and road congestion on
    the next tick.
    """
    result = SimulationService.force_spawn_incident(
        db,
        incident_type=payload.incident_type,
        severity=payload.severity,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    return ApiResponse.created(data=result, message="Incident spawned in simulation.")


# --- Engine Status Queries ---------------------------------------------------

@router.get(
    "/state",
    response_model=ApiResponse[SimulationStateResponse],
    summary="Get Digital Twin Engine status and metadata",
)
def get_simulation_state(
    _: User | None = Depends(get_optional_user),
) -> ApiResponse[SimulationStateResponse]:
    """
    Retrieve the operational state of the Digital Twin Engine.

    Returns engine metadata (running, tick count, active incidents, etc.)
    but not the full city state. Use GET /simulation/snapshot for the
    complete city state snapshot.
    """
    state = SimulationService.get_state()
    return ApiResponse.ok(data=state, message="Simulation state retrieved.")


@router.get(
    "/snapshot",
    response_model=ApiResponse[DigitalTwinCityState],
    summary="Get complete city state snapshot at current tick",
)
def get_city_snapshot(
    _: User | None = Depends(get_optional_user),
) -> ApiResponse[DigitalTwinCityState]:
    """
    Return the complete Digital Twin city state snapshot.

    Includes all citizen agents, building states, road segment statuses,
    weather conditions, and recent events from the current tick.
    This is a large payload — cache on the client side where possible.
    """
    from app.modules.simulation.engine import engine  # noqa: PLC0415

    snapshot = DigitalTwinCityState(
        tick_count=engine.tick_count,
        active_disasters_count=engine.active_disasters_count,
        total_citizens=len(engine.citizens),
        safe_citizens=sum(1 for c in engine.citizens if c.status.value == "SAFE"),
        endangered_citizens=sum(1 for c in engine.citizens if c.status.value == "ENDANGERED"),
        evacuating_citizens=sum(1 for c in engine.citizens if c.status.value == "EVACUATING"),
        injured_citizens=sum(1 for c in engine.citizens if c.status.value == "INJURED"),
        rescued_citizens=sum(1 for c in engine.citizens if c.status.value == "RESCUED"),
        weather=engine.weather,
        traffic=engine.traffic,
        buildings=engine.buildings,
        roads=engine.roads,
        citizens=engine.citizens,
        recent_events=engine.get_event_log()[:20],
    )
    return ApiResponse.ok(data=snapshot, message=f"Snapshot at tick {engine.tick_count}.")


@router.get(
    "/events",
    response_model=ApiResponse[list[SimulationEvent]],
    summary="Get recent simulation event log",
)
def get_event_log(
    limit: int = Query(default=50, ge=1, le=500, description="Max events to return"),
    _: User | None = Depends(get_optional_user),
) -> ApiResponse[list[SimulationEvent]]:
    """
    Return the most recent simulation events from the engine event log.

    The event log is a bounded ring buffer. Events are returned newest-first.
    Useful for the operations timeline panel in the dashboard.
    """
    from app.modules.simulation.engine import engine  # noqa: PLC0415

    events = engine.get_event_log()[:limit]
    return ApiResponse.ok(
        data=events,
        message=f"Retrieved {len(events)} events from tick {engine.tick_count}.",
    )


@router.get(
    "/citizens",
    response_model=ApiResponse[dict],
    summary="Get paginated citizen agent states",
)
def get_citizens(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    status_filter: str | None = Query(
        default=None,
        description="Filter by status: SAFE | ENDANGERED | EVACUATING | INJURED | RESCUED",
    ),
    _: User | None = Depends(get_optional_user),
) -> ApiResponse[dict]:
    """
    Return paginated citizen agent state from the digital twin.

    Optionally filter by citizen status to focus on at-risk populations.
    Useful for the city map overlay showing citizen heatmap.
    """
    from app.modules.simulation.engine import engine  # noqa: PLC0415

    citizens = engine.citizens
    if status_filter:
        citizens = [c for c in citizens if c.status.value == status_filter.upper()]

    total = len(citizens)
    skip = (page - 1) * page_size
    page_citizens = citizens[skip : skip + page_size]

    return ApiResponse.paginated(
        data=[c.model_dump() for c in page_citizens],
        total=total,
        page=page,
        page_size=page_size,
        message=f"Retrieved {len(page_citizens)} citizens.",
    )


@router.get(
    "/buildings",
    response_model=ApiResponse[list[BuildingState]],
    summary="Get all building states with damage tracking",
)
def get_buildings(
    damaged_only: bool = Query(default=False, description="Only return damaged buildings"),
    _: User | None = Depends(get_optional_user),
) -> ApiResponse[list[BuildingState]]:
    """
    Return the state of all buildings in the digital twin.

    Includes capacity, occupancy, damage percentage, and damage flag.
    Filter to damaged buildings only using the `damaged_only` parameter.
    """
    from app.modules.simulation.engine import engine  # noqa: PLC0415

    buildings = engine.buildings
    if damaged_only:
        buildings = [b for b in buildings if b.is_damaged]

    return ApiResponse.ok(
        data=buildings,
        message=f"Retrieved {len(buildings)} buildings.",
    )


# --- What-If Analysis & Comparative Scenario Engine --------------------------

@router.post(
    "/what-if/compare",
    response_model=ApiResponse[dict],
    summary="Run comparative What-If simulation analysis (COMMANDER+)",
)
def run_what_if_comparison(
    payload: dict,
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[dict]:
    """
    Run an isolated What-If scenario comparison against baseline response.

    Clones the current simulation city state into isolated sandboxes and executes
    multi-tick simulations under different intervention policies.
    """
    from app.modules.simulation.engine import engine  # noqa: PLC0415
    from app.modules.simulation.what_if import WhatIfEngine, WhatIfScenarioConfig  # noqa: PLC0415

    scenario_name = payload.get("name", "AI Dynamic Intervention")
    strategy = payload.get("strategy", "AI_DYNAMIC_EVACUATION")
    ticks = int(payload.get("ticks", 15))
    seed = int(payload.get("seed", 42))

    config = WhatIfScenarioConfig(
        name=scenario_name,
        strategy=strategy,
        evacuation_speed_multiplier=float(payload.get("evacuation_speed_multiplier", 1.5)),
        panic_reduction_factor=float(payload.get("panic_reduction_factor", 0.7)),
        shelter_capacity_multiplier=float(payload.get("shelter_capacity_multiplier", 1.2)),
        dispatch_priority_weight=float(payload.get("dispatch_priority_weight", 1.5)),
    )

    comparison = WhatIfEngine.run_comparison(
        base_citizens=engine.citizens,
        base_buildings=engine.buildings,
        base_roads=engine.roads,
        base_weather=engine.weather,
        intervened_config=config,
        ticks_to_simulate=ticks,
        random_seed=seed,
    )

    return ApiResponse.ok(
        data=comparison.model_dump(),
        message="What-If comparative scenario analysis completed.",
    )


# --- Simulation Replay & Timeline Endpoints ---------------------------------

@router.get(
    "/replay/history",
    response_model=ApiResponse[list],
    summary="Get recorded simulation replay timeline",
)
def get_replay_history(
    limit: int = Query(default=50, ge=1, le=500),
    _: User | None = Depends(get_optional_user),
) -> ApiResponse[list]:
    """Return historical tick snapshots recorded by the Replay Manager."""
    from app.modules.simulation.replay import replay_manager  # noqa: PLC0415

    history = replay_manager.get_history(limit=limit)
    return ApiResponse.ok(
        data=[s.model_dump(exclude={"state_snapshot"}) for s in history],
        message=f"Retrieved {len(history)} replay timeline snapshots.",
    )


@router.get(
    "/replay/tick/{target_tick}",
    response_model=ApiResponse[dict | None],
    summary="Seek and inspect historical snapshot at specific tick",
)
def seek_historical_tick(
    target_tick: int,
    _: User | None = Depends(get_optional_user),
) -> ApiResponse[dict | None]:
    """Retrieve full historical state snapshot at the given tick."""
    from app.modules.simulation.replay import replay_manager  # noqa: PLC0415

    snapshot = replay_manager.get_snapshot_by_tick(target_tick)
    if not snapshot:
        return ApiResponse.ok(data=None, message=f"No replay snapshot found for tick {target_tick}.")

    return ApiResponse.ok(
        data=snapshot.model_dump(),
        message=f"Replay state at tick {target_tick} retrieved.",
    )


@router.post(
    "/replay/checkpoint",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_201_CREATED,
    summary="Create a named checkpoint for simulation state (ADMIN/COMMANDER)",
)
def create_checkpoint(
    payload: dict,
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER"])),
) -> ApiResponse[dict]:
    """Save a named checkpoint of the current simulation state."""
    from app.modules.simulation.engine import engine  # noqa: PLC0415
    from app.modules.simulation.replay import replay_manager  # noqa: PLC0415

    name = payload.get("name", f"checkpoint_tick_{engine.tick_count}")
    snapshot = replay_manager.record_tick_snapshot(
        engine.tick_count,
        engine.get_snapshot(),
    )
    replay_manager.create_named_checkpoint(name, snapshot)

    return ApiResponse.created(
        data={"name": name, "tick": engine.tick_count},
        message=f"Checkpoint '{name}' created at tick {engine.tick_count}.",
    )

