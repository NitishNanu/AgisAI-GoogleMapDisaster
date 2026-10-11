"""
AegisAI / RescueNet AI — USGS Live Seismic Intelligence Feed.

Integrates USGS Real-time GeoJSON Earthquake API:
- Queries significant seismic events within operational bounding boxes.
- Maps epicenter, magnitude (M4.0+), depth, and tsunami flags.
"""

from typing import Any

import httpx
import structlog

logger = structlog.get_logger("aegis_ai.feeds.seismic")


class SeismicIntelligenceFeed:
    """
    Polls real-time seismic event feeds from USGS.
    """

    def __init__(self, feed_url: str = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"):
        self.feed_url = feed_url

    async def fetch_seismic_alerts(
        self,
        min_magnitude: float = 3.5,
        min_lat: float = 10.0,
        max_lat: float = 30.0,
        min_lon: float = 65.0,
        max_lon: float = 90.0,
    ) -> list[dict[str, Any]]:
        """
        Fetches live earthquakes and filters those within the specified geographic region.
        """
        alerts = []
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(self.feed_url)
                if resp.status_code == 200:
                    data = resp.json()
                    features = data.get("features", [])

                    for feat in features:
                        props = feat.get("properties", {})
                        geom = feat.get("geometry", {})
                        coords = geom.get("coordinates", [])

                        if len(coords) >= 2:
                            lon = float(coords[0])
                            lat = float(coords[1])
                            depth = float(coords[2]) if len(coords) > 2 else 10.0
                            mag = float(props.get("mag") or 0.0)
                            place = props.get("place", "Seismic Epicenter")

                            # Check regional bounds & magnitude
                            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon and mag >= min_magnitude:
                                severity = "CATASTROPHIC" if mag >= 7.0 else "CRITICAL" if mag >= 5.5 else "HIGH" if mag >= 4.5 else "MEDIUM"
                                alerts.append({
                                    "source": "USGS_SEISMIC_FEED",
                                    "disaster_type": "EARTHQUAKE",
                                    "severity": severity,
                                    "title": f"M{mag:.1f} Earthquake — {place}",
                                    "description": f"Magnitude {mag:.1f} seismic event at depth {depth:.1f} km. Epicenter: {place}.",
                                    "latitude": lat,
                                    "longitude": lon,
                                    "confidence": 0.99,
                                    "raw_telemetry": props,
                                })

        except Exception as e:
            logger.warning("seismic_feed_poll_failed", error=str(e))

        return alerts


seismic_feed = SeismicIntelligenceFeed()
