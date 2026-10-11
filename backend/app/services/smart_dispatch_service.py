"""
RescueNet AI — Smart Dispatch Service.

Orchestrates multi-stage dispatch intelligence:
1. PostGIS Top-K candidate selection (limit=5)
2. OSRM road routing (distance + ETA + geometry)
3. Multi-factor response compatibility scoring
4. Ranking and best available rescue team recommendation
"""

import asyncio
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.core.common.exceptions import EntityNotFoundException
from app.modules.incident.models import Incident
from app.routing.osrm import OSRMService
from app.services.geospatial_service import GeospatialService
from app.services.response_scoring_service import ResponseScoringService

logger = structlog.get_logger("aegis_ai.smart_dispatch")


class SmartDispatchService:
    """
    Smart Dispatch Service combining PostGIS proximity, OSRM road routing,
    and multi-factor response scoring.
    """

    @staticmethod
    async def get_recommended_teams(
        db: Session,
        disaster_id: int,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Rank candidate rescue teams for a given disaster.

        Flow:
        1. Find disaster.
        2. Query Top-K geographically closest AVAILABLE teams via PostGIS.
        3. For each candidate, call OSRM for road distance, ETA, and geometry.
        4. Calculate multi-factor response score.
        5. Sort by score descending and assign ranks.
        """
        incident = db.query(Incident).filter(Incident.id == disaster_id).first()
        if incident is None:
            raise EntityNotFoundException("Disaster", disaster_id)

        # 1. Top-K candidate selection using PostGIS
        candidates = GeospatialService.find_candidate_rescue_teams(
            db, disaster_id=disaster_id, limit=limit
        )

        if not candidates:
            return []

        # 2. Call OSRM concurrently for candidates only (bounded to limit K)
        async def fetch_candidate_route(team, straight_line_dist_meters):
            try:
                route_info = await OSRMService.get_route(
                    start_lat=team.latitude,
                    start_lon=team.longitude,
                    end_lat=incident.latitude,
                    end_lon=incident.longitude,
                )
                dist_km = float(route_info.get("distance_km", 0.0))
                eta_min = float(route_info.get("duration_minutes", 0.0))
                geom = route_info.get("geometry")
            except Exception as e:
                logger.warning(
                    "osrm_candidate_route_failed",
                    team_id=team.id,
                    disaster_id=disaster_id,
                    error=str(e),
                )
                direct_km = max(0.1, round(straight_line_dist_meters / 1000.0, 2))
                dist_km = round(direct_km * 1.3, 2)
                eta_min = max(1.0, round((dist_km / 40.0) * 60.0, 2))
                geom = {
                    "type": "LineString",
                    "coordinates": [
                        [team.longitude, team.latitude],
                        [incident.longitude, incident.latitude],
                    ],
                }

            score = ResponseScoringService.calculate_score(
                disaster_type=incident.disaster_type,
                vehicle_type=team.vehicle_type,
                distance_km=dist_km,
                eta_minutes=eta_min,
                status=team.status,
            )

            return {
                "team_id": team.id,
                "team_name": team.team_name,
                "vehicle_type": team.vehicle_type,
                "members": team.members,
                "status": team.status,
                "distance_km": dist_km,
                "eta_minutes": eta_min,
                "score": score,
                "route_geometry": geom,
            }

        tasks = [fetch_candidate_route(team, dist) for team, dist in candidates]
        ranked_teams = await asyncio.gather(*tasks)
        ranked_teams = list(ranked_teams)

        # 3. Sort by score descending
        ranked_teams.sort(key=lambda x: x["score"], reverse=True)

        for idx, item in enumerate(ranked_teams, start=1):
            item["rank"] = idx

        return ranked_teams


    @staticmethod
    async def get_dispatch_recommendation(
        db: Session,
        disaster_id: int,
        limit: int = 5,
    ) -> dict[str, Any]:
        """
        Return the standardized recommendation payload.
        """
        teams = await SmartDispatchService.get_recommended_teams(
            db, disaster_id=disaster_id, limit=limit
        )

        return {
            "success": True,
            "disaster_id": disaster_id,
            "count": len(teams),
            "recommended_team": teams[0] if teams else None,
            "teams": teams,
        }
