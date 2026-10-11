"""Analytics Service Unit Tests."""


from app.modules.analytics.schemas import (
    DashboardSummary,
    EmergencyAnalyticsSummary,
    ResourceUtilizationReport,
)


class TestDashboardSummary:
    def test_dashboard_summary_returns_correct_type(self, mocker):
        mock_db = mocker.MagicMock()

        # Mock all DB queries
        mock_db.query.return_value.filter.return_value.count.return_value = 5
        mock_db.query.return_value.filter.return_value.filter.return_value.count.return_value = 2
        mock_db.query.return_value.count.return_value = 10
        mock_db.query.return_value.filter.return_value.scalar.return_value = 500

        from app.modules.analytics.service import AnalyticsService
        summary = AnalyticsService.get_dashboard_summary(mock_db)
        assert isinstance(summary, DashboardSummary)

    def test_dashboard_has_non_negative_values(self, mocker):
        mock_db = mocker.MagicMock()
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        mock_db.query.return_value.filter.return_value.filter.return_value.count.return_value = 0
        mock_db.query.return_value.count.return_value = 0
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        from app.modules.analytics.service import AnalyticsService
        summary = AnalyticsService.get_dashboard_summary(mock_db)
        assert summary.total_active_incidents >= 0
        assert summary.available_rescue_teams >= 0
        assert summary.total_hospitals >= 0


class TestIncidentBreakdowns:
    def test_type_breakdown_returns_list(self, mocker):
        mock_repo = mocker.MagicMock()
        mock_repo.count_incidents_by_type.return_value = [
            {"type": "FIRE", "count": 3},
            {"type": "FLOOD", "count": 2},
        ]
        mocker.patch(
            "app.modules.analytics.service.AnalyticsRepository",
            return_value=mock_repo,
        )
        mock_db = mocker.MagicMock()

        from app.modules.analytics.service import AnalyticsService
        result = AnalyticsService.get_incident_breakdown_by_type(mock_db)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["type"] == "FIRE"
        assert result[0]["count"] == 3

    def test_severity_breakdown_returns_list(self, mocker):
        mock_repo = mocker.MagicMock()
        mock_repo.count_incidents_by_severity.return_value = [
            {"severity": "CRITICAL", "count": 4},
        ]
        mocker.patch(
            "app.modules.analytics.service.AnalyticsRepository",
            return_value=mock_repo,
        )
        mock_db = mocker.MagicMock()

        from app.modules.analytics.service import AnalyticsService
        result = AnalyticsService.get_incident_breakdown_by_severity(mock_db)
        assert len(result) == 1
        assert result[0]["severity"] == "CRITICAL"


class TestResourceUtilization:
    def test_resource_utilization_report_structure(self, mocker):
        mock_repo = mocker.MagicMock()
        mock_repo.get_team_utilization.return_value = {
            "total": 6, "available": 4, "dispatched": 2,
            "on_standby": 0, "utilization_percent": 33.3,
        }
        mock_repo.get_shelter_utilization.return_value = {
            "total_shelters": 6, "total_capacity": 4500,
            "total_occupancy": 1190, "available_capacity": 3310,
            "occupancy_percent": 26.4,
        }
        mock_repo.get_hospital_summary.return_value = {
            "total": 5, "operational": 5, "offline": 0,
            "total_beds": 2450, "total_icu_beds": 385, "with_oxygen": 5,
        }
        mock_repo.get_recent_assignments.return_value = []

        mocker.patch(
            "app.modules.analytics.service.AnalyticsRepository",
            return_value=mock_repo,
        )
        mock_db = mocker.MagicMock()

        from app.modules.analytics.service import AnalyticsService
        report = AnalyticsService.get_resource_utilization_report(mock_db)
        assert isinstance(report, ResourceUtilizationReport)
        assert report.teams.total == 6
        assert report.shelters.total_shelters == 6
        assert report.hospitals.total == 5


class TestLegacySummary:
    def test_emergency_summary_returns_correct_type(self, mocker):
        mock_db = mocker.MagicMock()
        mock_db.query.return_value.filter.return_value.count.return_value = 3
        mock_db.query.return_value.count.return_value = 8
        mock_db.query.return_value.scalar.return_value = 1000

        from app.modules.analytics.service import AnalyticsService
        result = AnalyticsService.get_emergency_summary(mock_db)
        assert isinstance(result, EmergencyAnalyticsSummary)
        assert result.system_health_score == 99.9
