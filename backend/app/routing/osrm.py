"""
AegisAI — OSRM Road Routing Service.

Calls the OSRM routing engine for real road distance, travel time, and
turn-by-turn geometry between two WGS84 coordinate pairs.

Falls back to a Haversine straight-line estimate (×1.3 road-factor heuristic)
if the OSRM service is unavailable or returns an error.

Configuration (from settings):
  OSRM_BASE_URL             — Base URL of the OSRM instance (default: public demo)
  OSRM_TIMEOUT_SECONDS      — HTTP request timeout in seconds (default: 5.0)
"""

import math

import httpx
import structlog

from app.core.config.settings import settings

logger = structlog.get_logger("aegis_ai.routing.osrm")


def calculate_haversine_fallback(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> dict:
    """
    Haversine great-circle distance with a 1.3× road-factor heuristic.

    Used when OSRM is unreachable. Returns the same shape as a real OSRM
    response so callers need no special-case logic.
    """
    r_earth = 6371.0
    dlat = math.radians(end_lat - start_lat)
    dlon = math.radians(end_lon - start_lon)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(start_lat))
        * math.cos(math.radians(end_lat))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    direct_km = r_earth * c
    road_km = max(0.1, round(direct_km * 1.3, 2))
    eta_minutes = max(1.0, round((road_km / 40.0) * 60.0, 2))

    return {
        "distance_km": road_km,
        "duration_minutes": eta_minutes,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [start_lon, start_lat],
                [end_lon, end_lat],
            ],
        },
    }


class OSRMService:
    """
    OSRM HTTP client.

    All methods are static. The OSRM endpoint and timeout are sourced from
    AppSettings so they can be overridden via environment variable:

        OSRM_BASE_URL=http://my-osrm-server:5000
        OSRM_TIMEOUT_SECONDS=10
    """

    @staticmethod
    async def get_route(
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
    ) -> dict:
        """
        Fetch road route from OSRM between two coordinate pairs.

        Returns a dict with:
          - distance_km      : float — road distance in kilometres
          - duration_minutes : float — estimated travel time in minutes
          - geometry         : dict  — GeoJSON LineString of the route

        Falls back to Haversine estimate on any network or API error.
        """
        coordinates = f"{start_lon},{start_lat};{end_lon},{end_lat}"
        url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{coordinates}"
        params = {
            "overview": "full",
            "geometries": "geojson",
            "steps": "false",
        }

        try:
            async with httpx.AsyncClient(timeout=settings.OSRM_TIMEOUT_SECONDS) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                return {
                    "distance_km": round(route["distance"] / 1000, 2),
                    "duration_minutes": round(route["duration"] / 60, 2),
                    "geometry": route["geometry"],
                }

        except Exception as error:
            logger.warning(
                "osrm_request_failed_using_haversine_fallback",
                osrm_url=url,
                error=str(error),
            )

        return calculate_haversine_fallback(
            start_lat=start_lat,
            start_lon=start_lon,
            end_lat=end_lat,
            end_lon=end_lon,
        )
