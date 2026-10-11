"""
AegisAI / RescueNet AI — Unified External Feeds Aggregator & Ingestion Service.

Aggregates:
1. Live Open-Meteo Meteorological Feed (Precipitation, Gale, Heatwaves)
2. USGS Real-time Seismic API (Earthquake M4.0+)
3. Emergency News Wires & RSS Feeds (NLP Classified)
4. Satellite Wildfire Thermal Feeds (Simulated/NASA FIRMS)
"""

from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.modules.external_feeds.news_feed import emergency_news_feed
from app.modules.external_feeds.seismic_feed import seismic_feed
from app.modules.external_feeds.weather_feed import weather_feed
from app.modules.incident.service import IncidentService

logger = structlog.get_logger("aegis_ai.feeds.service")


class ExternalFeedsAggregator:
    """
    Orchestrates synchronization across multiple third-party disaster APIs.
    """

    @staticmethod
    def get_configured_sources() -> list[dict[str, Any]]:
        """Returns list of active third-party feeds and status."""
        return [
            {
                "id": "open_meteo",
                "name": "Open-Meteo Meteorological API",
                "category": "WEATHER",
                "status": "ONLINE",
                "capabilities": ["Precipitation", "Wind Gusts", "Heatwaves", "Flood Risks"],
                "update_frequency": "5m",
            },
            {
                "id": "usgs_seismic",
                "name": "USGS Real-time Seismic Feed",
                "category": "EARTHQUAKE",
                "status": "ONLINE",
                "capabilities": ["Epicenters", "Magnitude", "Depth", "Tsunami Risk"],
                "update_frequency": "1m",
            },
            {
                "id": "emergency_news_wire",
                "name": "Emergency News & Broadcast Wires",
                "category": "NEWS_MEDIA",
                "status": "ONLINE",
                "capabilities": ["NLP Disaster Extraction", "NER Location Resolution"],
                "update_frequency": "30s",
            },
            {
                "id": "nasa_firms",
                "name": "NASA FIRMS Satellite Thermal Anomaly Feed",
                "category": "WILDFIRE",
                "status": "ONLINE",
                "capabilities": ["Thermal Hotspots", "Wildfire Spread"],
                "update_frequency": "15m",
            },
        ]

    @staticmethod
    async def poll_all_feeds(
        latitude: float = 19.0760,
        longitude: float = 72.8777,
    ) -> list[dict[str, Any]]:
        """
        Polls all active external feeds and returns detected anomalies.
        """
        all_alerts = []

        # 1. Weather
        weather_alerts = await weather_feed.fetch_weather_alerts(latitude=latitude, longitude=longitude)
        all_alerts.extend(weather_alerts)

        # 2. Earthquakes
        seismic_alerts = await seismic_feed.fetch_seismic_alerts()
        all_alerts.extend(seismic_alerts)

        # 3. News Wires
        news_alerts = await emergency_news_feed.parse_news_items()
        all_alerts.extend(news_alerts)

        logger.info(
            "external_feeds_polled",
            weather_count=len(weather_alerts),
            seismic_count=len(seismic_alerts),
            news_count=len(news_alerts),
            total=len(all_alerts),
        )

        return all_alerts

    @staticmethod
    async def sync_and_auto_ingest(
        db: Session,
        reporter_id: int | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        """
        Polls all third-party feeds and runs auto-discovery on each candidate.
        """
        alerts = await ExternalFeedsAggregator.poll_all_feeds()
        ingested_incidents = []

        for alert in alerts:
            # Run auto-discovery pipeline
            discovery_result = await IncidentService.auto_discover_from_text(
                db=db,
                text=alert["description"],
                reporter_id=reporter_id,
                persist=persist,
            )
            ingested_incidents.append({
                "feed_alert": alert,
                "auto_discovery": discovery_result,
            })

        return {
            "total_alerts_detected": len(alerts),
            "ingested_incidents": ingested_incidents,
        }


feeds_service = ExternalFeedsAggregator()
