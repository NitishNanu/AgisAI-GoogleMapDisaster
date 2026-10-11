"""
AegisAI Scenario Module — Domain Service.
Handles scenario lifecycle, database persistence, cloning, What-If compatibility, and Digital Twin launch.
Python 3.10 compatible.
"""

import copy
import random
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.common.exceptions import (
    ConflictException,
    EntityNotFoundException,
    ValidationException,
)
from app.core.websocket.manager import ws_manager
from app.modules.scenario.enums import ScenarioRunStatus, ScenarioStatus
from app.modules.scenario.models import Scenario, ScenarioRun
from app.modules.scenario.presets import get_scenario_presets
from app.modules.scenario.risk_scorer import BaselineRiskScorer
from app.modules.scenario.schemas import (
    PresetResponse,
    ScenarioCreateRequest,
    ScenarioPreviewResponse,
    ScenarioUpdateRequest,
    ScenarioValidateResponse,
)
from app.modules.scenario.validator import ScenarioValidator
from app.modules.simulation.engine import engine as twin_engine

logger = structlog.get_logger("aegis_ai.scenario.service")


class ScenarioService:
    """Enterprise domain service managing the scenario lifecycle."""

    @classmethod
    def validate_scenario(cls, payload: ScenarioCreateRequest) -> ScenarioValidateResponse:
        """Validate scenario payload against boundary and domain rules."""
        return ScenarioValidator.validate(payload)

    @classmethod
    def preview_scenario(cls, payload: ScenarioCreateRequest) -> ScenarioPreviewResponse:
        """Compute estimated casualties, shelter/hospital demands, and risk score."""
        val_res = cls.validate_scenario(payload)
        if not val_res.is_valid:
            error_msgs = "; ".join(f"{e.field}: {e.message}" for e in val_res.errors)
            raise ValidationException(f"Invalid scenario configuration: {error_msgs}")
        return BaselineRiskScorer.calculate_preview(payload)

    @classmethod
    def get_presets(cls) -> list[PresetResponse]:
        """Return standardized scenario presets."""
        return get_scenario_presets()

    @classmethod
    def create_scenario(
        cls,
        db: Session,
        payload: ScenarioCreateRequest,
        user_id: int | None = None,
    ) -> Scenario:
        """Persist a new disaster scenario blueprint."""
        val_res = cls.validate_scenario(payload)
        if not val_res.is_valid:
            error_msgs = "; ".join(f"{e.field}: {e.message}" for e in val_res.errors)
            raise ValidationException(f"Scenario validation failed: {error_msgs}")

        scenario_id = str(uuid.uuid4())
        random_seed = payload.simulation.random_seed or random.randint(1000, 999999)

        scenario = Scenario(
            id=scenario_id,
            name=payload.name,
            description=payload.description,
            status=ScenarioStatus.READY.value,
            created_by=user_id,
            disaster_type=payload.disaster.type.upper(),
            severity=payload.disaster.severity.value,
            latitude=payload.disaster.latitude,
            longitude=payload.disaster.longitude,
            radius_km=payload.disaster.radius_km,
            population_count=payload.population.count,
            simulation_duration_minutes=payload.simulation.duration_minutes,
            simulation_speed=payload.simulation.speed,
            random_seed=random_seed,
            disaster_config=payload.disaster.model_dump(),
            environment_config=payload.environment.model_dump(),
            population_config=payload.population.model_dump(),
            resource_config=payload.resources.model_dump(),
            hospital_config=payload.hospitals.model_dump(),
            shelter_config=payload.shelters.model_dump(),
            infrastructure_config=payload.infrastructure.model_dump(),
            simulation_config=payload.simulation.model_dump(),
            is_template=payload.is_template,
            simulation_engine_version="2.0.0",
            scenario_schema_version="1.0.0",
        )

        db.add(scenario)
        db.commit()
        db.refresh(scenario)

        logger.info(
            "scenario_created",
            scenario_id=scenario.id,
            name=scenario.name,
            disaster_type=scenario.disaster_type,
            user_id=user_id,
        )

        return scenario

    @classmethod
    def get_scenarios(
        cls,
        db: Session,
        skip: int = 0,
        limit: int = 50,
        status: str | None = None,
        disaster_type: str | None = None,
        severity: str | None = None,
        is_template: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[Scenario], int]:
        """Query scenarios with pagination and filtering."""
        query = select(Scenario).where(Scenario.status != ScenarioStatus.ARCHIVED.value)

        if status:
            query = query.where(Scenario.status == status.upper())
        if disaster_type:
            query = query.where(Scenario.disaster_type == disaster_type.upper())
        if severity:
            query = query.where(Scenario.severity == severity.upper())
        if is_template is not None:
            query = query.where(Scenario.is_template == is_template)
        if search:
            query = query.where(
                or_(
                    Scenario.name.ilike(f"%{search}%"),
                    Scenario.description.ilike(f"%{search}%"),
                )
            )

        total = len(db.scalars(query).all())
        scenarios = db.scalars(query.order_by(Scenario.created_at.desc()).offset(skip).limit(limit)).all()

        return list(scenarios), total

    @classmethod
    def get_scenario(cls, db: Session, scenario_id: str) -> Scenario:
        """Fetch scenario by ID or raise EntityNotFoundException."""
        scenario = db.scalar(select(Scenario).where(Scenario.id == scenario_id))
        if not scenario:
            raise EntityNotFoundException("Scenario", scenario_id)
        return scenario

    @classmethod
    def update_scenario(
        cls,
        db: Session,
        scenario_id: str,
        payload: ScenarioUpdateRequest,
        user_id: int | None = None,
    ) -> Scenario:
        """Update scenario details (only permitted in DRAFT or READY state)."""
        scenario = cls.get_scenario(db, scenario_id)

        if scenario.status == ScenarioStatus.RUNNING.value:
            raise ConflictException("Cannot modify a scenario while its simulation is actively running.")

        if payload.name is not None:
            scenario.name = payload.name
        if payload.description is not None:
            scenario.description = payload.description
        if payload.disaster is not None:
            scenario.disaster_type = payload.disaster.type.upper()
            scenario.severity = payload.disaster.severity.value
            scenario.latitude = payload.disaster.latitude
            scenario.longitude = payload.disaster.longitude
            scenario.radius_km = payload.disaster.radius_km
            scenario.disaster_config = payload.disaster.model_dump()
        if payload.environment is not None:
            scenario.environment_config = payload.environment.model_dump()
        if payload.population is not None:
            scenario.population_count = payload.population.count
            scenario.population_config = payload.population.model_dump()
        if payload.resources is not None:
            scenario.resource_config = payload.resources.model_dump()
        if payload.hospitals is not None:
            scenario.hospital_config = payload.hospitals.model_dump()
        if payload.shelters is not None:
            scenario.shelter_config = payload.shelters.model_dump()
        if payload.infrastructure is not None:
            scenario.infrastructure_config = payload.infrastructure.model_dump()
        if payload.simulation is not None:
            scenario.simulation_duration_minutes = payload.simulation.duration_minutes
            scenario.simulation_speed = payload.simulation.speed
            scenario.random_seed = payload.simulation.random_seed
            scenario.simulation_config = payload.simulation.model_dump()
        if payload.is_template is not None:
            scenario.is_template = payload.is_template

        db.commit()
        db.refresh(scenario)

        logger.info("scenario_updated", scenario_id=scenario_id, user_id=user_id)
        return scenario

    @classmethod
    def archive_scenario(cls, db: Session, scenario_id: str, user_id: int | None = None) -> None:
        """Soft-delete/archive a scenario."""
        scenario = cls.get_scenario(db, scenario_id)
        scenario.status = ScenarioStatus.ARCHIVED.value
        db.commit()
        logger.info("scenario_archived", scenario_id=scenario_id, user_id=user_id)

    @classmethod
    def clone_scenario(
        cls,
        db: Session,
        scenario_id: str,
        new_name: str | None = None,
        user_id: int | None = None,
    ) -> Scenario:
        """Clone an existing scenario with a new UUID for What-If scenario branching."""
        original = cls.get_scenario(db, scenario_id)

        cloned_name = new_name or f"{original.name} (Clone)"
        cloned_id = str(uuid.uuid4())

        cloned = Scenario(
            id=cloned_id,
            name=cloned_name,
            description=f"Cloned from scenario '{original.name}' ({original.id})",
            status=ScenarioStatus.READY.value,
            created_by=user_id,
            disaster_type=original.disaster_type,
            severity=original.severity,
            latitude=original.latitude,
            longitude=original.longitude,
            radius_km=original.radius_km,
            population_count=original.population_count,
            simulation_duration_minutes=original.simulation_duration_minutes,
            simulation_speed=original.simulation_speed,
            random_seed=random.randint(1000, 999999),
            disaster_config=copy.deepcopy(original.disaster_config),
            environment_config=copy.deepcopy(original.environment_config),
            population_config=copy.deepcopy(original.population_config),
            resource_config=copy.deepcopy(original.resource_config),
            hospital_config=copy.deepcopy(original.hospital_config),
            shelter_config=copy.deepcopy(original.shelter_config),
            infrastructure_config=copy.deepcopy(original.infrastructure_config),
            simulation_config=copy.deepcopy(original.simulation_config),
            is_template=False,
            simulation_engine_version=original.simulation_engine_version,
            scenario_schema_version=original.scenario_schema_version,
        )

        db.add(cloned)
        db.commit()
        db.refresh(cloned)

        logger.info("scenario_cloned", original_id=scenario_id, clone_id=cloned.id, user_id=user_id)
        return cloned

    @classmethod
    async def launch_scenario(
        cls,
        db: Session,
        scenario_id: str,
        user_id: int | None = None,
    ) -> ScenarioRun:
        """
        Launch a scenario simulation run.

        1. Validates scenario state.
        2. Configures the authoritative DigitalTwinEngine with the scenario's disaster,
           weather conditions, traffic penalties, and random seed.
        3. Creates a ScenarioRun record with initial snapshot.
        4. Broadcasts SCENARIO_LAUNCHED to all connected WebSocket clients.
        """
        scenario = cls.get_scenario(db, scenario_id)

        # 1. Capture initial snapshot from digital twin
        initial_snapshot = twin_engine.get_snapshot().model_dump()

        # 2. Configure Digital Twin Engine
        env_conf = scenario.environment_config or {}
        if env_conf:
            twin_engine.weather.temperature_celsius = float(env_conf.get("temperature_celsius", 28.0))
            twin_engine.weather.wind_speed_kmh = float(env_conf.get("wind_speed_kmh", 15.0))
            twin_engine.weather.humidity_percent = float(env_conf.get("humidity_percent", 60.0))
            twin_engine.weather.visibility_km = float(env_conf.get("visibility_km", 10.0))
            twin_engine.weather.condition = str(env_conf.get("weather_preset", "CLEAR"))

        # Inject disaster coordinates into engine proximity tracker
        twin_engine.force_add_disaster(
            lat=scenario.latitude,
            lon=scenario.longitude,
            severity=scenario.severity,
        )

        # Start simulation engine
        twin_engine.is_running = True

        # 3. Create ScenarioRun Record
        run_id = str(uuid.uuid4())
        run = ScenarioRun(
            id=run_id,
            scenario_id=scenario.id,
            status=ScenarioRunStatus.RUNNING.value,
            random_seed=scenario.random_seed,
            simulation_engine_version=scenario.simulation_engine_version,
            started_at=datetime.now(timezone.utc),
            initial_state_snapshot=initial_snapshot,
            final_state_snapshot={},
            metrics={
                "disaster_type": scenario.disaster_type,
                "severity": scenario.severity,
                "affected_population": scenario.population_count,
            },
        )

        scenario.status = ScenarioStatus.RUNNING.value
        db.add(run)
        db.commit()
        db.refresh(run)

        # 4. Broadcast Real-Time Event
        event_payload = {
            "scenario_id": scenario.id,
            "scenario_name": scenario.name,
            "run_id": run.id,
            "disaster_type": scenario.disaster_type,
            "severity": scenario.severity,
            "latitude": scenario.latitude,
            "longitude": scenario.longitude,
            "radius_km": scenario.radius_km,
            "seed": scenario.random_seed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            await ws_manager.broadcast_to_channel("all", "SCENARIO_LAUNCHED", event_payload)
            await ws_manager.broadcast_to_channel("simulation", "SCENARIO_LAUNCHED", event_payload)
        except Exception as ws_err:
            logger.warning("scenario_launch_ws_broadcast_failed", error=str(ws_err))

        logger.info("scenario_launched", scenario_id=scenario.id, run_id=run.id, user_id=user_id)
        return run

    @classmethod
    def get_scenario_runs(cls, db: Session, scenario_id: str) -> list[ScenarioRun]:
        """Fetch historical runs for a scenario."""
        runs = db.scalars(
            select(ScenarioRun)
            .where(ScenarioRun.scenario_id == scenario_id)
            .order_by(ScenarioRun.created_at.desc())
        ).all()
        return list(runs)
