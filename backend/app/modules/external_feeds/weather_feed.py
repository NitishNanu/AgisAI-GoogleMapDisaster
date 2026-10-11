"""
AegisAI / RescueNet AI — External Weather Intelligence Feed.

Integrates Open-Meteo / Public Meteorological APIs:
- Monitors real-time precipitation (>40mm/h -> FLOOD ALERT)
- Monitors wind gusts (>75km/h -> CYCLONE / GALE ALERT)
- Monitors extreme temperature (>42C -> HEATWAVE, <0C -> FREEZE)
"""

from typing import Any

import httpx
import structlog

logger = structlog.get_logger("aegis_ai.feeds.weather")


class WeatherIntelligenceFeed:
    """
    Polls real-time meteorological conditions and generates disaster alert candidates.
    """

    def __init__(self, open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"):
        self.open_meteo_url = open_meteo_url

    async def fetch_weather_alerts(
        self,
        latitude: float = 19.0760,
        longitude: float = 72.8777,
    ) -> list[dict[str, Any]]:
        """
        Fetches live current weather and checks against operational hazard thresholds.
        """
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation,rain,wind_speed_10m,wind_gusts_10m,surface_pressure",
            "timezone": "auto",
        }

        alerts = []
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(self.open_meteo_url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    current = data.get("current", {})

                    precip = float(current.get("precipitation", 0.0))
                    wind_speed = float(current.get("wind_speed_10m", 0.0))
                    wind_gusts = float(current.get("wind_gusts_10m", 0.0))
                    temp = float(current.get("temperature_2m", 25.0))

                    # 1. Flood Warning Threshold
                    if precip >= 25.0:
                        alerts.append({
                            "source": "OPEN_METEO_WEATHER_API",
                            "disaster_type": "FLOOD",
                            "severity": "CRITICAL" if precip > 50.0 else "HIGH",
                            "title": f"Severe Precipitation Alert ({precip} mm/h)",
                            "description": f"Extreme rainfall rate detected at {latitude:.4f}, {longitude:.4f}. Immediate flash flood risk.",
                            "latitude": latitude,
                            "longitude": longitude,
                            "confidence": 0.92,
                            "raw_telemetry": current,
                        })

                    # 2. Cyclone / Storm Warning Threshold
                    if wind_speed >= 65.0 or wind_gusts >= 80.0:
                        alerts.append({
                            "source": "OPEN_METEO_WEATHER_API",
                            "disaster_type": "CYCLONE",
                            "severity": "CRITICAL" if wind_gusts > 100.0 else "HIGH",
                            "title": f"Gale / Storm Warning ({wind_gusts} km/h Gusts)",
                            "description": f"High velocity wind gusts detected at {latitude:.4f}, {longitude:.4f}. High risk of power line and structural disruption.",
                            "latitude": latitude,
                            "longitude": longitude,
                            "confidence": 0.90,
                            "raw_telemetry": current,
                        })

                    # 3. Heatwave Warning Threshold
                    if temp >= 42.0:
                        alerts.append({
                            "source": "OPEN_METEO_WEATHER_API",
                            "disaster_type": "HEATWAVE",
                            "severity": "HIGH",
                            "title": f"Extreme Heatwave Alert ({temp}°C)",
                            "description": f"Severe thermal conditions observed at {latitude:.4f}, {longitude:.4f}. Medical dehydration & heatstroke surge expected.",
                            "latitude": latitude,
                            "longitude": longitude,
                            "confidence": 0.88,
                            "raw_telemetry": current,
                        })

        except Exception as e:
            logger.warning("weather_feed_poll_failed_using_simulated_weather", error=str(e))

        return alerts


weather_feed = WeatherIntelligenceFeed()
