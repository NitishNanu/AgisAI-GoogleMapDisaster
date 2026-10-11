"""
AegisAI / RescueNet AI — Geocoding & Administrative Boundary Validation Pipeline.

Pipeline:
Raw Report -> NER -> Location Candidates -> Geocoder -> Administrative Boundary Validation -> Confidence Scoring.
"""

import httpx
import structlog

logger = structlog.get_logger("aegis_ai.nlp.geocoder")

# Default bounding box for Aegis City / simulation region
DEFAULT_ADMIN_BOUNDS = {
    "min_lat": 18.0,
    "max_lat": 20.5,
    "min_lon": 72.0,
    "max_lon": 74.5,
}


class DisasterGeocoder:
    """
    Nominatim-compatible geocoding service with boundary verification and confidence scoring.
    """

    def __init__(self, nominatim_url: str = "https://nominatim.openstreetmap.org"):
        self.nominatim_url = nominatim_url
        self.bounds = DEFAULT_ADMIN_BOUNDS

    async def geocode_candidate(self, location_text: str) -> dict[str, any] | None:
        """
        Geocodes a candidate location name and validates against boundaries.
        """
        if not location_text or len(location_text.strip()) < 3:
            return None

        # Check for sector/zone synthetic matches first
        synthetic_match = self._match_synthetic_zone(location_text)
        if synthetic_match:
            return synthetic_match

        try:
            headers = {"User-Agent": "AegisAI-Disaster-Response-Platform/1.0"}
            params = {
                "q": location_text,
                "format": "json",
                "limit": 1,
            }
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"{self.nominatim_url}/search", params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data and len(data) > 0:
                        first = data[0]
                        lat = float(first["lat"])
                        lon = float(first["lon"])
                        confidence = float(first.get("importance", 0.75))

                        is_within_bounds = self._is_within_bounds(lat, lon)
                        return {
                            "latitude": lat,
                            "longitude": lon,
                            "address": first.get("display_name", location_text),
                            "confidence": confidence if is_within_bounds else max(0.2, confidence - 0.4),
                            "provider": "NOMINATIM",
                            "status": "VALIDATED" if is_within_bounds else "NEEDS_REVIEW",
                        }
        except Exception as e:
            logger.warning("geocoding_lookup_failed", location=location_text, error=str(e))

        return None

    def _is_within_bounds(self, lat: float, lon: float) -> bool:
        return (
            self.bounds["min_lat"] <= lat <= self.bounds["max_lat"]
            and self.bounds["min_lon"] <= lon <= self.bounds["max_lon"]
        )

    def _match_synthetic_zone(self, text: str) -> dict[str, any] | None:
        """Matches standard Aegis City digital twin grid references."""
        import re
        match = re.search(r"Sector\s+(\d+)", text, re.IGNORECASE)
        if match:
            sector_num = int(match.group(1))
            # Deterministic coordinate map for simulation sectors
            base_lat = 19.0760 + (sector_num % 10) * 0.015
            base_lon = 72.8777 + (sector_num // 10) * 0.015
            return {
                "latitude": round(base_lat, 6),
                "longitude": round(base_lon, 6),
                "address": f"Aegis Metro Sector {sector_num}",
                "confidence": 0.95,
                "provider": "AEGIS_CITY_GRID",
                "status": "VALIDATED",
            }
        return None


disaster_geocoder = DisasterGeocoder()
