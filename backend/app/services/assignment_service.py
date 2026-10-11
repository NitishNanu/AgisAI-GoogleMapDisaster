"""
RescueNet AI — Assignment & Mission Lifecycle Service.

Provides transaction-safe dispatching, state machine validation,
timestamp recording, team release, and disaster status synchronization.
"""

import json
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.core.common.exceptions import (
    ConflictException,
    EntityNotFoundException,
    ValidationException,
)
from app.modules.incident.models import Incident
from app.modules.resource.models import RescueTeam, ResourceAssignment

logger = structlog.get_logger("aegis_ai.assignment_service")

# State machine: Valid mission transitions
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "ASSIGNED": {"DISPATCHED", "CANCELLED", "EN_ROUTE"},
    "DISPATCHED": {"EN_ROUTE", "CANCELLED"},
    "EN_ROUTE": {"ARRIVED", "CANCELLED"},
    "ARRIVED": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}

ACTIVE_MISSION_STATUSES = {"ASSIGNED", "DISPATCHED", "EN_ROUTE", "ARRIVED"}


class AssignmentService:
    """
    Service managing mission assignments, transaction-safe dispatching,
    and state transitions.
    """

    @staticmethod
    def create_assignment(
        db: Session,
        incident_id: int,
        team_id: int,
        dispatched_by: int,
        notes: str | None = None,
        estimated_arrival_minutes: float | None = None,
        distance_km: float | None = None,
        route_geometry: Any = None,
    ) -> ResourceAssignment:
        """
        Create a new mission assignment with transaction safety.

        Steps:
        1. Verify disaster exists (SELECT FOR UPDATE — row-level lock prevents TOCTOU).
        2. Verify team exists (SELECT FOR UPDATE).
        3. Verify team is AVAILABLE.
        4. Verify disaster does not already have an active assignment.
        5. Create assignment.
        6. Update team status to DISPATCHED.
        7. Update disaster status to RESPONDING.
        8. Commit transaction.

        The two SELECT FOR UPDATE locks ensure that concurrent dispatch requests
        for the same incident or team are serialized at the DB level, eliminating
        the check-then-act race condition.
        """
        # 1. Verify disaster — row-level lock prevents concurrent double-dispatch
        incident = (
            db.query(Incident)
            .filter(Incident.id == incident_id)
            .with_for_update()
            .first()
        )
        if incident is None:
            raise EntityNotFoundException("Disaster", incident_id)

        # 2. Verify team — row-level lock prevents concurrent double-assignment
        team = (
            db.query(RescueTeam)
            .filter(RescueTeam.id == team_id)
            .with_for_update()
            .first()
        )
        if team is None:
            raise EntityNotFoundException("RescueTeam", team_id)

        # 3. Check team availability
        if team.status != "AVAILABLE":
            raise ConflictException(
                f"Rescue team {team.id} ({team.team_name}) is currently {team.status} and cannot be assigned."
            )

        # 4. Check if disaster already has an active assignment
        existing_active = (
            db.query(ResourceAssignment)
            .filter(
                ResourceAssignment.incident_id == incident_id,
                ResourceAssignment.status.in_(list(ACTIVE_MISSION_STATUSES)),
            )
            .first()
        )
        if existing_active:
            raise ConflictException(
                f"Disaster {incident_id} already has an active mission (Assignment #{existing_active.id}, status: {existing_active.status})."
            )

        # Format geometry string if dict/list passed
        geom_str = None
        if route_geometry:
            geom_str = json.dumps(route_geometry) if isinstance(route_geometry, (dict, list)) else str(route_geometry)

        # 5. Create assignment
        assignment = ResourceAssignment(
            incident_id=incident_id,
            team_id=team_id,
            dispatched_by=dispatched_by,
            status="ASSIGNED",
            estimated_arrival_minutes=estimated_arrival_minutes,
            distance_km=distance_km,
            route_geometry=geom_str,
            notes=notes,
        )
        db.add(assignment)

        # 6. Update team status
        team.status = "DISPATCHED"

        # 7. Update disaster status to RESPONDING
        if incident.status == "ACTIVE":
            incident.status = "RESPONDING"

        # 8. Commit
        db.commit()
        db.refresh(assignment)

        logger.info(
            "mission_dispatched",
            assignment_id=assignment.id,
            incident_id=incident_id,
            team_id=team_id,
            dispatched_by=dispatched_by,
        )

        return assignment

    @staticmethod
    def update_assignment_status(
        db: Session,
        assignment_id: int,
        new_status: str,
        notes: str | None = None,
    ) -> ResourceAssignment:
        """
        Transition assignment to a new status following the mission state machine.

        Validates allowed transitions, updates mission timestamps, updates
        rescue team status, and synchronizes disaster lifecycle state.
        """
        # H4 FIX: SELECT FOR UPDATE prevents concurrent status transition race
        # conditions. Two concurrent callers both seeing the same current_status
        # and both passing the transition guard was a real lost-update bug.
        assignment = (
            db.query(ResourceAssignment)
            .filter(ResourceAssignment.id == assignment_id)
            .with_for_update()
            .first()
        )
        if assignment is None:
            raise EntityNotFoundException("ResourceAssignment", assignment_id)

        target_status = new_status.upper().strip()
        current_status = assignment.status.upper().strip()

        # Idempotent no-op if status hasn't changed
        if current_status == target_status:
            if notes is not None:
                assignment.notes = notes
                db.commit()
                db.refresh(assignment)
            return assignment

        # Validate transition
        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise ValidationException(
                f"Invalid mission status transition: '{current_status}' -> '{target_status}'. Allowed transitions: {sorted(allowed) or 'None (terminal state)'}"
            )

        now = datetime.now(timezone.utc)
        assignment.status = target_status
        if notes is not None:
            assignment.notes = notes

        # Update timestamps
        if target_status == "EN_ROUTE" and assignment.started_at is None:
            assignment.started_at = now
        elif target_status in ("COMPLETED", "CANCELLED"):
            assignment.completed_at = now

        # Synchronize team status — lock the row before mutating to prevent
        # concurrent assignments from overwriting status in opposite order.
        team = (
            db.query(RescueTeam)
            .filter(RescueTeam.id == assignment.team_id)
            .with_for_update()
            .first()
        )
        if team:
            if target_status in ("COMPLETED", "CANCELLED"):
                team.status = "AVAILABLE"
            elif target_status == "ARRIVED":
                team.status = "ON_SCENE"
            elif target_status in ("DISPATCHED", "EN_ROUTE"):
                team.status = "DISPATCHED"

        # Synchronize disaster status
        incident = db.query(Incident).filter(Incident.id == assignment.incident_id).first()
        if incident:
            # Check for other active assignments for this disaster
            other_active = (
                db.query(ResourceAssignment)
                .filter(
                    ResourceAssignment.incident_id == assignment.incident_id,
                    ResourceAssignment.id != assignment.id,
                    ResourceAssignment.status.in_(list(ACTIVE_MISSION_STATUSES)),
                )
                .count()
            )

            if target_status == "COMPLETED":
                if other_active == 0:
                    incident.status = "RESOLVED"
            elif target_status == "CANCELLED":
                if other_active == 0:
                    incident.status = "ACTIVE"

        db.commit()
        db.refresh(assignment)

        logger.info(
            "mission_status_updated",
            assignment_id=assignment_id,
            old_status=current_status,
            new_status=target_status,
        )

        return assignment

    @staticmethod
    def get_assignment(db: Session, assignment_id: int) -> ResourceAssignment:
        assignment = (
            db.query(ResourceAssignment)
            .filter(ResourceAssignment.id == assignment_id)
            .first()
        )
        if assignment is None:
            raise EntityNotFoundException("ResourceAssignment", assignment_id)
        return assignment
