"""
AegisAI Analytics Module — API Router.

Provides the Mission Control analytics API with 7 endpoints:

  GET  /api/v1/analytics/dashboard              — Real-time platform KPI summary
  GET  /api/v1/analytics/incidents/by-type      — Incident count by disaster type
  GET  /api/v1/analytics/incidents/by-severity  — Incident count by severity
  GET  /api/v1/analytics/incidents/by-status    — Incident count by lifecycle status
  GET  /api/v1/analytics/resources/utilization  — Teams, shelters, hospital utilization
  GET  /api/v1/analytics/reports                — Paginated list of stored reports
  POST /api/v1/analytics/reports                — Generate and persist a new report
  GET  /api/v1/analytics/reports/{id}           — Retrieve a specific stored report
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.common.response import ApiResponse
from app.core.database.session import get_db
from app.core.security.jwt import RequireRole, get_current_active_user
from app.modules.analytics.schemas import (
    AnalyticsReportResponse,
    DashboardSummary,
    GenerateReportRequest,
    ResourceUtilizationReport,
)
from app.modules.analytics.service import AnalyticsService
from app.modules.auth.models import User

router = APIRouter(prefix="/analytics", tags=["Analytics & Reporting"])


@router.get(
    "/dashboard",
    response_model=ApiResponse[DashboardSummary],
    summary="Mission Control real-time KPI dashboard",
)
def get_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> ApiResponse[DashboardSummary]:
    """
    Aggregate cross-module KPIs for the emergency operations dashboard.

    Returns active incident count, critical incidents, hospital and shelter
    availability, and rescue team dispatch status in a single call.
    Designed for low-latency polling from the frontend dashboard.
    """
    summary = AnalyticsService.get_dashboard_summary(db)
    return ApiResponse.ok(data=summary, message="Dashboard KPIs retrieved.")


@router.get(
    "/incidents/by-type",
    response_model=ApiResponse[list],
    summary="Incident breakdown by disaster type",
)
def incidents_by_type(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> ApiResponse[list]:
    """
    Return incident counts grouped by disaster type.

    Useful for bar/pie charts on the analytics dashboard.
    Results are ordered by frequency (most common type first).
    """
    breakdown = AnalyticsService.get_incident_breakdown_by_type(db)
    return ApiResponse.ok(
        data=breakdown,
        message=f"Incident type breakdown: {len(breakdown)} categories.",
    )


@router.get(
    "/incidents/by-severity",
    response_model=ApiResponse[list],
    summary="Incident breakdown by severity level",
)
def incidents_by_severity(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> ApiResponse[list]:
    """
    Return incident counts grouped by severity (LOW / MEDIUM / HIGH / CRITICAL).

    Useful for understanding the current threat profile of the platform.
    """
    breakdown = AnalyticsService.get_incident_breakdown_by_severity(db)
    return ApiResponse.ok(
        data=breakdown,
        message=f"Incident severity breakdown: {len(breakdown)} levels.",
    )


@router.get(
    "/incidents/by-status",
    response_model=ApiResponse[list],
    summary="Incident breakdown by lifecycle status",
)
def incidents_by_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> ApiResponse[list]:
    """
    Return incident counts grouped by operational status
    (REPORTED, INVESTIGATING, RESPONDING, RESOLVED, CANCELLED).
    """
    breakdown = AnalyticsService.get_incident_breakdown_by_status(db)
    return ApiResponse.ok(
        data=breakdown,
        message=f"Incident status breakdown: {len(breakdown)} statuses.",
    )


@router.get(
    "/resources/utilization",
    response_model=ApiResponse[ResourceUtilizationReport],
    summary="Cross-module resource utilization report",
)
def resource_utilization(
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[ResourceUtilizationReport]:
    """
    Return a detailed resource utilization report covering:
      - Rescue team availability and dispatch rates
      - Shelter capacity and occupancy percentages
      - Hospital operational status and bed counts
      - Last 10 resource assignment records
    """
    report = AnalyticsService.get_resource_utilization_report(db)
    return ApiResponse.ok(data=report, message="Resource utilization report generated.")


@router.get(
    "/reports",
    response_model=ApiResponse[dict],
    summary="List persisted analytics reports (ADMIN/COMMANDER)",
)
def list_reports(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Reports per page"),
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER"])),
) -> ApiResponse[dict]:
    """
    Return a paginated list of all persisted analytics report snapshots.

    Reports are ordered newest-first. Each report represents a point-in-time
    snapshot of all platform KPIs.
    """
    reports, total = AnalyticsService.list_reports(db, page=page, page_size=page_size)
    items = [AnalyticsReportResponse.model_validate(r).model_dump() for r in reports]
    return ApiResponse.paginated(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
        message=f"Retrieved {len(items)} reports.",
    )


@router.post(
    "/reports",
    response_model=ApiResponse[AnalyticsReportResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate and persist a new analytics report (ADMIN/COMMANDER)",
)
def generate_report(
    body: GenerateReportRequest,
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER"])),
) -> ApiResponse[AnalyticsReportResponse]:
    """
    Trigger generation of a full platform analytics report.

    Aggregates all cross-module KPIs at the current moment and persists
    the snapshot to the database. Includes incident breakdowns by type
    and severity, resource utilization, and system health score.
    """
    report = AnalyticsService.generate_full_report(db, title=body.title)
    return ApiResponse.created(data=report, message="Analytics report generated and stored.")


@router.get(
    "/reports/{report_id}",
    response_model=ApiResponse[AnalyticsReportResponse],
    summary="Retrieve a specific analytics report (ADMIN/COMMANDER)",
)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER"])),
) -> ApiResponse[AnalyticsReportResponse]:
    """
    Retrieve a previously generated analytics report by its ID.

    Useful for comparing historical snapshots or sharing a specific
    report with stakeholders.
    """
    report = AnalyticsService.get_report(db, report_id)
    return ApiResponse.ok(
        data=AnalyticsReportResponse.model_validate(report),
        message="Analytics report retrieved.",
    )


@router.get(
    "/aar/incident/{incident_id}",
    response_model=ApiResponse[dict | None],
    summary="Generate Incident After-Action Report (AAR)",
)
def get_incident_aar(
    incident_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER", "DISPATCHER"])),
) -> ApiResponse[dict | None]:
    """Generate structured After-Action Review (AAR) for an incident."""
    from app.modules.analytics.reports_engine import ReportsEngine  # noqa: PLC0415

    aar = ReportsEngine.generate_incident_aar(db, incident_id)
    if not aar:
        return ApiResponse.ok(data=None, message=f"Incident #{incident_id} not found.")

    return ApiResponse.ok(data=aar.model_dump(), message="After-Action Report generated.")


@router.get(
    "/audit/hospitals",
    response_model=ApiResponse[dict],
    summary="Generate comprehensive hospital readiness audit",
)
def get_hospital_audit(
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER", "MEDIC"])),
) -> ApiResponse[dict]:
    """Generate system-wide hospital capacity and readiness audit."""
    from app.modules.analytics.reports_engine import ReportsEngine  # noqa: PLC0415

    audit = ReportsEngine.generate_hospital_capacity_audit(db)
    return ApiResponse.ok(data=audit, message="Hospital readiness audit generated.")


@router.get(
    "/export/incidents/csv",
    summary="Export incidents dataset as CSV",
)
def export_incidents_csv(
    db: Session = Depends(get_db),
    _: User = Depends(RequireRole(["ADMIN", "COMMANDER"])),
):
    """Export all incidents in CSV format."""
    from fastapi.responses import Response  # noqa: PLC0415

    from app.modules.analytics.reports_engine import ReportsEngine  # noqa: PLC0415

    csv_data = ReportsEngine.export_incidents_csv(db)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=incidents_export.csv"},
    )

