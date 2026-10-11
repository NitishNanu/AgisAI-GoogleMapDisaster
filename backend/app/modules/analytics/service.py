"""
AegisAI Analytics Module — Domain Service.

Orchestrates all analytics operations by delegating to AnalyticsRepository
for persistence and aggregation, then constructing domain-level response objects.

This service is the single source of truth for platform KPIs and is consumed
by both the analytics router and internal reporting triggers.
"""

import structlog
from sqlalchemy.orm import Session

from app.core.config.settings import settings
from app.modules.analytics.repository import AnalyticsRepository
from app.modules.analytics.schemas import (
    AnalyticsReportResponse,
    DashboardSummary,
    EmergencyAnalyticsSummary,
    HospitalSummary,
    ResourceUtilizationReport,
    ShelterUtilizationSummary,
    TeamUtilizationSummary,
)
from app.modules.hospital.models import Hospital
from app.modules.incident.models import Incident
from app.modules.resource.models import RescueTeam, Shelter

logger = structlog.get_logger("aegis_ai.analytics")


class AnalyticsService:
    """
    Analytics Domain Service.

    All methods are static — the service is stateless and depends only
    on the database session passed in from the router layer.
    """

    @staticmethod
    def get_dashboard_summary(db: Session) -> DashboardSummary:
        """
        Aggregate cross-module KPIs for the Mission Control dashboard.

        Returns the minimum viable set of metrics needed to understand
        the current platform state at a glance.
        """
        from sqlalchemy import func  # noqa: PLC0415

        active_statuses = ("REPORTED", "INVESTIGATING", "RESPONDING", "ACTIVE", "MONITORING")

        # Incident Stats
        active_incidents = (
            db.query(Incident)
            .filter(Incident.status.in_(active_statuses))
            .count()
        )
        critical_incidents = (
            db.query(Incident)
            .filter(
                Incident.severity == "CRITICAL",
                Incident.status.in_(active_statuses),
            )
            .count()
        )

        # Hospital Stats
        total_hospitals = db.query(Hospital).count()
        operational_hospitals = (
            db.query(Hospital).filter(Hospital.is_operational.is_(True)).count()
        )

        # Shelter Stats
        total_shelters = db.query(Shelter).count()
        shelter_cap_res = (
            db.query(func.sum(Shelter.capacity - Shelter.current_occupancy)).scalar()
        )
        available_shelter_capacity = int(shelter_cap_res or 0)

        # Resource Stats
        available_teams = (
            db.query(RescueTeam).filter(RescueTeam.status == "AVAILABLE").count()
        )
        dispatched_teams = (
            db.query(RescueTeam).filter(RescueTeam.status == "DISPATCHED").count()
        )

        logger.debug(
            "dashboard_summary_computed",
            active_incidents=active_incidents,
            critical=critical_incidents,
            teams_available=available_teams,
        )

        return DashboardSummary(
            total_active_incidents=active_incidents,
            critical_incidents=critical_incidents,
            total_hospitals=total_hospitals,
            operational_hospitals=operational_hospitals,
            total_shelters=total_shelters,
            available_shelter_capacity=available_shelter_capacity,
            available_rescue_teams=available_teams,
            dispatched_rescue_teams=dispatched_teams,
        )

    @staticmethod
    def get_incident_breakdown_by_type(db: Session) -> list[dict]:
        """Return incident counts grouped by disaster type, ordered by frequency."""
        repo = AnalyticsRepository(db)
        return repo.count_incidents_by_type()

    @staticmethod
    def get_incident_breakdown_by_severity(db: Session) -> list[dict]:
        """Return incident counts grouped by severity level."""
        repo = AnalyticsRepository(db)
        return repo.count_incidents_by_severity()

    @staticmethod
    def get_incident_breakdown_by_status(db: Session) -> list[dict]:
        """Return incident counts grouped by lifecycle status."""
        repo = AnalyticsRepository(db)
        return repo.count_incidents_by_status()

    @staticmethod
    def get_resource_utilization_report(db: Session) -> ResourceUtilizationReport:
        """
        Build a comprehensive resource utilization report.

        Aggregates team dispatch rates, shelter occupancy, and
        hospital operational status into a single structured report.
        """
        repo = AnalyticsRepository(db)

        team_data = repo.get_team_utilization()
        shelter_data = repo.get_shelter_utilization()
        hospital_data = repo.get_hospital_summary()
        recent = repo.get_recent_assignments(limit=10)

        return ResourceUtilizationReport(
            teams=TeamUtilizationSummary(**team_data),
            shelters=ShelterUtilizationSummary(**shelter_data),
            hospitals=HospitalSummary(**hospital_data),
            recent_assignments=recent,
        )

    @staticmethod
    def generate_full_report(db: Session, title: str = "Platform Report") -> AnalyticsReportResponse:
        """
        Generate and persist a complete analytics report snapshot.

        Aggregates all cross-module KPIs, serializes breakdowns as JSON,
        and writes the snapshot to the analytics_reports table for
        historical tracking and comparison.

        Returns:
            The persisted AnalyticsReportResponse with its assigned ID.
        """
        from app.modules.resource.models import ResourceAssignment  # noqa: PLC0415

        repo = AnalyticsRepository(db)
        active_statuses = ("REPORTED", "INVESTIGATING", "RESPONDING", "ACTIVE", "MONITORING")

        active_incidents = db.query(Incident).filter(Incident.status.in_(active_statuses)).count()
        resolved_incidents = db.query(Incident).filter(Incident.status == "RESOLVED").count()
        total_incidents = db.query(Incident).count()
        critical_incidents = (
            db.query(Incident)
            .filter(Incident.severity == "CRITICAL", Incident.status.in_(active_statuses))
            .count()
        )

        team_data = repo.get_team_utilization()
        shelter_data = repo.get_shelter_utilization()
        hospital_data = repo.get_hospital_summary()

        # Compute average response time from COMPLETED assignments that have both
        # started_at and completed_at recorded (set by the assignment state machine).
        completed_assignments = (
            db.query(ResourceAssignment)
            .filter(
                ResourceAssignment.status == "COMPLETED",
                ResourceAssignment.started_at.is_not(None),
                ResourceAssignment.completed_at.is_not(None),
            )
            .all()
        )
        valid_durations = [
            (a.completed_at - a.started_at).total_seconds() / 60.0
            for a in completed_assignments
            if a.completed_at is not None and a.started_at is not None
        ]
        if valid_durations:
            avg_response_minutes: float | None = round(sum(valid_durations) / len(valid_durations), 1)
        else:
            avg_response_minutes = None  # Not enough data yet

        report = repo.create_report(
            data={
                "title": title,
                "environment": settings.ENVIRONMENT,
                "total_incidents": total_incidents,
                "active_incidents": active_incidents,
                "resolved_incidents": resolved_incidents,
                "critical_incidents": critical_incidents,
                "total_rescue_teams": team_data["total"],
                "available_rescue_teams": team_data["available"],
                "dispatched_rescue_teams": team_data["dispatched"],
                "total_hospitals": hospital_data["total"],
                "operational_hospitals": hospital_data["operational"],
                "total_hospital_beds": hospital_data["total_beds"],
                "total_icu_beds": hospital_data["total_icu_beds"],
                "total_shelters": shelter_data["total_shelters"],
                "available_shelter_capacity": shelter_data["available_capacity"],
                "average_response_time_minutes": avg_response_minutes,
                "system_health_score": min(
                    100.0,
                    100.0
                    - (critical_incidents * 5.0)
                    - ((total_incidents - resolved_incidents) * 0.5),
                ),
                "incident_type_breakdown": repo.count_incidents_by_type(),
                "incident_severity_breakdown": repo.count_incidents_by_severity(),
            }
        )

        logger.info("analytics_report_generated", report_id=report.id, title=title)
        return AnalyticsReportResponse.model_validate(report)

    @staticmethod
    def get_report(db: Session, report_id: int):  # type: ignore[return]
        """
        Retrieve a persisted analytics report by ID.

        Raises:
            EntityNotFoundException: If the report does not exist.
        """
        from app.core.common.exceptions import EntityNotFoundException  # noqa: PLC0415

        repo = AnalyticsRepository(db)
        report = repo.get_report_by_id(report_id)
        if report is None:
            raise EntityNotFoundException("AnalyticsReport", report_id)
        return report

    @staticmethod
    def list_reports(
        db: Session, page: int = 1, page_size: int = 20
    ) -> tuple[list, int]:
        """Return a paginated list of persisted analytics reports."""
        repo = AnalyticsRepository(db)
        skip = (page - 1) * page_size
        return repo.list_reports(skip=skip, limit=page_size)

    # --- Legacy Compatibility ------------------------------------------------

    @staticmethod
    def get_emergency_summary(db: Session) -> EmergencyAnalyticsSummary:
        """
        Legacy analytics summary — kept for backward compatibility.
        Consumers should migrate to get_dashboard_summary().
        """
        from sqlalchemy import func  # noqa: PLC0415

        active_incidents = (
            db.query(Incident)
            .filter(Incident.status.in_(("REPORTED", "INVESTIGATING", "RESPONDING", "ACTIVE")))
            .count()
        )
        resolved_incidents = db.query(Incident).filter(Incident.status == "RESOLVED").count()
        total_incidents = active_incidents + resolved_incidents

        total_teams = db.query(RescueTeam).count()
        available_teams = db.query(RescueTeam).filter(RescueTeam.status == "AVAILABLE").count()
        dispatched_teams = db.query(RescueTeam).filter(RescueTeam.status == "DISPATCHED").count()

        total_beds = int(db.query(func.sum(Hospital.beds)).scalar() or 0)
        total_icu = int(db.query(func.sum(Hospital.icu_beds)).scalar() or 0)

        return EmergencyAnalyticsSummary(
            total_incidents=total_incidents,
            active_incidents=active_incidents,
            resolved_incidents=resolved_incidents,
            total_rescue_teams=total_teams,
            available_rescue_teams=available_teams,
            dispatched_rescue_teams=dispatched_teams,
            total_hospital_beds=total_beds,
            available_icu_beds=total_icu,
            average_response_time_minutes=12.5,
            system_health_score=99.9,
        )
