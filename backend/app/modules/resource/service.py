"""AegisAI Resource Module â€” Domain Service."""

import structlog
from sqlalchemy.orm import Session

from app.core.common.exceptions import (
    ConflictException,
    EntityNotFoundException,
    ValidationException,
)
from app.modules.resource.models import RescueTeam, ResourceAssignment, Shelter
from app.modules.resource.repository import ResourceRepository
from app.modules.resource.schemas import (
    AssignmentCreate,
    AssignmentUpdate,
    RescueTeamCreate,
    RescueTeamUpdate,
    ShelterCreate,
    ShelterUpdate,
)

logger = structlog.get_logger("aegis_ai.resource")


class ResourceService:
    """Resource management domain service."""

    # -----------------------------------------------------------------------
    # Rescue Teams
    # -----------------------------------------------------------------------
    @staticmethod
    def create_team(db: Session, payload: RescueTeamCreate) -> RescueTeam:
        repo = ResourceRepository(db)

        # Check for unique team name
        existing, _ = repo.get_teams(limit=1000)
        if any(t.team_name == payload.team_name for t in existing):
            raise ConflictException(f"Team name '{payload.team_name}' already exists.")

        team = repo.create_team(**payload.model_dump())
        logger.info("rescue_team_created", team_id=team.id, name=team.team_name)
        return team

    @staticmethod
    def get_team(db: Session, team_id: int) -> RescueTeam:
        team = ResourceRepository(db).get_team(team_id)
        if not team:
            raise EntityNotFoundException("RescueTeam", team_id)
        return team

    @staticmethod
    def list_teams(db: Session, page: int = 1, page_size: int = 50, status_filter: str | None = None) -> tuple[list[RescueTeam], int]:
        repo = ResourceRepository(db)
        skip = (page - 1) * page_size
        return repo.get_teams(skip=skip, limit=page_size, status_filter=status_filter)

    @staticmethod
    def update_team(db: Session, team_id: int, payload: RescueTeamUpdate) -> RescueTeam:
        repo = ResourceRepository(db)
        team = repo.update_team(team_id, payload.model_dump(exclude_none=True))
        if not team:
            raise EntityNotFoundException("RescueTeam", team_id)
        logger.info("rescue_team_updated", team_id=team_id)
        return team

    @staticmethod
    def delete_team(db: Session, team_id: int) -> None:
        if not ResourceRepository(db).delete_team(team_id):
            raise EntityNotFoundException("RescueTeam", team_id)
        logger.info("rescue_team_deleted", team_id=team_id)

    # -----------------------------------------------------------------------
    # Shelters
    # -----------------------------------------------------------------------
    @staticmethod
    def create_shelter(db: Session, payload: ShelterCreate) -> Shelter:
        shelter = ResourceRepository(db).create_shelter(**payload.model_dump())
        logger.info("shelter_created", shelter_id=shelter.id)
        return shelter

    @staticmethod
    def get_shelter(db: Session, shelter_id: int) -> Shelter:
        shelter = ResourceRepository(db).get_shelter(shelter_id)
        if not shelter:
            raise EntityNotFoundException("Shelter", shelter_id)
        return shelter

    @staticmethod
    def list_shelters(db: Session, page: int = 1, page_size: int = 50, available_only: bool = False) -> tuple[list[Shelter], int]:
        skip = (page - 1) * page_size
        return ResourceRepository(db).get_shelters(skip=skip, limit=page_size, available_only=available_only)

    @staticmethod
    def update_shelter(db: Session, shelter_id: int, payload: ShelterUpdate) -> Shelter:
        repo = ResourceRepository(db)
        existing = repo.get_shelter(shelter_id)
        if not existing:
            raise EntityNotFoundException("Shelter", shelter_id)

        updates = payload.model_dump(exclude_none=True)

        new_cap = updates.get("capacity", existing.capacity)
        new_occ = updates.get("current_occupancy", existing.current_occupancy)
        if new_occ > new_cap:
            raise ValidationException("Occupancy cannot exceed capacity.")

        shelter = repo.update_shelter(shelter_id, updates)
        if not shelter:
            raise EntityNotFoundException("Shelter", shelter_id)
        logger.info("shelter_updated", shelter_id=shelter_id)
        return shelter

    @staticmethod
    def delete_shelter(db: Session, shelter_id: int) -> None:
        if not ResourceRepository(db).delete_shelter(shelter_id):
            raise EntityNotFoundException("Shelter", shelter_id)
        logger.info("shelter_deleted", shelter_id=shelter_id)

    # -----------------------------------------------------------------------
    # Assignments
    # -----------------------------------------------------------------------
    @staticmethod
    def dispatch_team(db: Session, payload: AssignmentCreate, dispatcher_id: int) -> ResourceAssignment:
        from app.services.assignment_service import AssignmentService  # noqa: PLC0415
        return AssignmentService.create_assignment(
            db=db,
            incident_id=payload.incident_id,
            team_id=payload.team_id,
            dispatched_by=dispatcher_id,
            notes=payload.notes,
            estimated_arrival_minutes=payload.estimated_arrival_minutes,
            distance_km=payload.distance_km,
            route_geometry=payload.route_geometry,
        )

    @staticmethod
    def update_assignment_status(db: Session, assignment_id: int, payload: AssignmentUpdate) -> ResourceAssignment:
        from app.services.assignment_service import AssignmentService  # noqa: PLC0415
        target_status = payload.status.value if payload.status and hasattr(payload.status, "value") else (str(payload.status) if payload.status else None)
        if target_status:
            return AssignmentService.update_assignment_status(
                db=db,
                assignment_id=assignment_id,
                new_status=target_status,
                notes=payload.notes,
            )
        else:
            repo = ResourceRepository(db)
            assignment = repo.update_assignment(assignment_id, payload.model_dump(exclude_none=True))
            if not assignment:
                raise EntityNotFoundException("ResourceAssignment", assignment_id)
            return assignment

