"""
Tests for External Third-Party Disaster Intelligence Feeds (Weather, USGS Earthquakes, News Wires).
"""

import asyncio

from app.modules.external_feeds.news_feed import emergency_news_feed
from app.modules.external_feeds.service import feeds_service


def test_configured_sources_list():
    sources = feeds_service.get_configured_sources()
    assert len(sources) >= 3
    source_ids = [s["id"] for s in sources]
    assert "open_meteo" in source_ids
    assert "usgs_seismic" in source_ids
    assert "emergency_news_wire" in source_ids


def test_emergency_news_wire_nlp_processing():
    news_samples = [
        {
            "source": "Local Daily",
            "headline": "Massive fire and explosions at warehouse in Sector 10, multiple units responding",
        },
        {
            "source": "Routine Post",
            "headline": "City park opens new flower exhibition today",
        }
    ]
    alerts = asyncio.run(emergency_news_feed.parse_news_items(news_samples))
    # Disaster item should be detected, flower exhibition ignored
    assert len(alerts) == 1
    assert alerts[0]["disaster_type"] in ["FIRE", "INDUSTRIAL_ACCIDENT"]
    assert alerts[0]["confidence"] > 0.0
    assert 18.0 <= alerts[0]["latitude"] <= 21.0
