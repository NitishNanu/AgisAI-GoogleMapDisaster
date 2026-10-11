"""
RescueNet AI — Geospatial Service.

Provides spatial search and PostGIS-backed proximity queries for candidate
rescue team selection and distance filtering.
"""

import math
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.common.exceptions import EntityNotFoundException
from app.modules.incident.models import Incident
from app.modules.resource.models import RescueTeam


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance in meters between two WGS84 coordinates."""
    r = 6371000.0  # Earth radius in meters
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    return r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


class GeospatialService:
    """
    Geospatial service providing spatial filtering, proximity searches,
    and PostGIS Top-K candidate selection.
    """

    @staticmethod
    def find_candidate_rescue_teams(
        db: Session,
        disaster_id: int,
        limit: int = 5,
    ) -> list[tuple[RescueTeam, float]]:
        """
        Find top-K geographically closest AVAILABLE rescue teams using PostGIS spatial distance.

        Steps:
        1. Find the disaster/incident.
        2. Filter rescue teams to AVAILABLE.
        3. Calculate geographic distance using ST_Distance.
        4. Order by distance ascending.
        5. Limit to K (default 5).
        6. Return candidate teams and geographic distance in meters.
        """
        incident = db.query(Incident).filter(Incident.id == disaster_id).first()
        if incident is None:
            raise EntityNotFoundException("Disaster", disaster_id)

        # Attempt PostGIS spatial distance query
        try:
            if incident.location is not None:
                distance_expr = func.ST_Distance(RescueTeam.location, incident.location)
                results = (
                    db.query(RescueTeam, distance_expr.label("distance_meters"))
                    .filter(RescueTeam.status == "AVAILABLE")
                    .order_by(distance_expr)
                    .limit(limit)
                    .all()
                )
                return [(team, float(dist or 0.0)) for team, dist in results]
        except Exception:
            # Fallback for environments without PostGIS (e.g. SQLite unit tests)
            pass

        # Fallback calculation using Python Haversine
        available_teams = db.query(RescueTeam).filter(RescueTeam.status == "AVAILABLE").all()
        team_distances: list[tuple[RescueTeam, float]] = []

        for team in available_teams:
            dist_m = haversine_distance_meters(
                team.latitude, team.longitude, incident.latitude, incident.longitude
            )
            team_distances.append((team, round(dist_m, 2)))

        team_distances.sort(key=lambda x: x[1])
        return team_distances[:limit]

    @staticmethod
    def get_nearest_rescue_team(
        db: Session,
        disaster_id: int,
    ) -> dict[str, Any] | None:
        """Find the single nearest available rescue team."""
        candidates = GeospatialService.find_candidate_rescue_teams(db, disaster_id, limit=1)
        if not candidates:
            return None

        team, distance_m = candidates[0]
        return {
            "team_id": team.id,
            "team_name": team.team_name,
            "vehicle_type": team.vehicle_type,
            "members": team.members,
            "status": team.status,
            "latitude": team.latitude,
            "longitude": team.longitude,
            "distance_meters": round(distance_m, 2),
        }
