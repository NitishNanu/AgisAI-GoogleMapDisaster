"""AegisAI Simulation Module â€” Domain Service."""

import structlog
from sqlalchemy.orm import Session

from app.modules.simulation.engine import engine
from app.modules.simulation.schemas import (
    SimulationActionRequest,
    SimulationConfig,
    SimulationStateResponse,
)

logger = structlog.get_logger("aegis_ai.simulation")


class SimulationService:
    """Domain service bridging the API and the DigitalTwinEngine singleton."""

    @staticmethod
    def get_state() -> SimulationStateResponse:
        """Get the current simulation engine state and configuration."""
        return SimulationStateResponse(
            is_running=engine.is_running,
            current_tick=engine.tick_count,
            active_incidents=engine.active_disasters_count,
            available_resources=0,  # Could be dynamically counted from DB
            config=engine.config,
            last_tick_time=engine.last_tick_time,
        )

    @staticmethod
    def update_config(payload: SimulationConfig) -> SimulationStateResponse:
        """Apply new runtime configuration to the running engine."""
        engine.update_config(payload)
        return SimulationService.get_state()

    @staticmethod
    async def perform_action(action_req: SimulationActionRequest) -> SimulationStateResponse:
        """Execute a control action on the Digital Twin Engine."""
        action = action_req.action

        if action in ("start", "resume"):
            engine.is_running = True
            logger.info("simulation_started")
        elif action in ("stop", "pause"):
            engine.is_running = False
            logger.info("simulation_stopped")
        elif action == "tick":
            # Force a tick regardless of running state
            await engine.tick()
        elif action == "reset":
            engine.reset()
            logger.info("simulation_reset")

        return SimulationService.get_state()

    @staticmethod
    def force_spawn_incident(
        db: Session,
        incident_type: str,
        severity: str,
        latitude: float,
        longitude: float,
        affected_radius_meters: float = 1000.0,
        reporter_id: int | None = None,
    ) -> dict:
        """
        Force-spawn a simulated incident.

        1. Creates a proper Incident record in the DB via IncidentService.
        2. Registers the location in the engine's disaster proximity tracker
           so citizens and roads react on the next tick.
        """
        from app.modules.auth.models import User  # noqa: PLC0415
        from app.modules.incident.enums import DisasterType, SeverityLevel  # noqa: PLC0415
        from app.modules.incident.schemas import IncidentCreate  # noqa: PLC0415
        from app.modules.incident.service import IncidentService  # noqa: PLC0415

        # Fallback to first available system/admin user if reporter_id not supplied or invalid
        effective_reporter_id = reporter_id
        if not effective_reporter_id:
            user = db.query(User).filter(User.role.in_(["ADMIN", "COMMANDER", "DISPATCHER"])).first()
            if not user:
                user = db.query(User).first()
            effective_reporter_id = user.id if user else 1

        payload = IncidentCreate(
            title=f"Simulated {incident_type} Event",
            description="Automatically spawned by the Digital Twin simulation engine.",
            disaster_type=DisasterType(incident_type),
            severity=SeverityLevel(severity),
            latitude=latitude,
            longitude=longitude,
            affected_radius_meters=affected_radius_meters,
        )

        incident = IncidentService.report_incident(db, payload, reporter_id=effective_reporter_id)

        # Register in the engine's proximity tracker for citizen/road simulation
        engine.force_add_disaster(lat=latitude, lon=longitude, severity=severity)

        logger.info(
            "simulation_incident_spawned",
            incident_id=incident.id,
            type=incident_type,
            severity=severity,
        )

        return {
            "status": "spawned",
            "incident_id": incident.id,
            "type": incident.disaster_type,
            "severity": incident.severity,
            "latitude": incident.latitude,
            "longitude": incident.longitude,
        }
