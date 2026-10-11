"""
AegisAI / RescueNet AI — Emergency News & Social Wire Feed.

Cuts through breaking emergency wires & RSS feeds:
- Ingests emergency dispatch bulletins, local breaking news headers.
- Runs NLP Classifier (TF-IDF + Entity Extraction + Geocoder) on news text.
- Converts confirmed news alerts into disaster incident candidates.
"""

from typing import Any

import structlog

from app.modules.ai.nlp.classifier import disaster_nlp_classifier
from app.modules.ai.nlp.extractor import emergency_entity_extractor
from app.modules.ai.nlp.geocoder import disaster_geocoder

logger = structlog.get_logger("aegis_ai.feeds.news")

# Standard breaking news wire samples for simulation/monitoring
DEFAULT_EMERGENCY_WIRE_ITEMS = [
    {
        "source": "Emergency News Network",
        "headline": "Massive fire reported at industrial chemical storage in Sector 9, black plumes visible for miles",
        "timestamp": "Just now",
    },
    {
        "source": "City Traffic & Transit Wire",
        "headline": "Major highway overpass blocked due to mud landslide near Sector 16 hills following relentless storm",
        "timestamp": "5m ago",
    },
    {
        "source": "Coastal Defense Authority",
        "headline": "High tidal storm surge flooding low-lying streets across Sector 3 marina, citizens advised to evacuate",
        "timestamp": "12m ago",
    },
]


class EmergencyNewsFeed:
    """
    Parses breaking news wires and extracts actionable emergency alerts using NLP.
    """

    async def parse_news_items(
        self,
        news_items: list[dict[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Parses list of headlines/news reports and runs full NLP triage.
        """
        items_to_process = news_items or DEFAULT_EMERGENCY_WIRE_ITEMS
        alerts = []

        for item in items_to_process:
            headline = item.get("headline", "")
            source_name = item.get("source", "NEWS_WIRE")

            # 1. NLP Classification
            cls_result = disaster_nlp_classifier.predict(headline)
            disaster_type = cls_result["predicted_class"]

            # Ignore non-disasters
            if disaster_type == "OTHER" or cls_result["confidence"] < 0.25:
                continue

            # 2. NER & Geocoding
            entities = emergency_entity_extractor.extract_entities(headline)
            locations = entities.get("locations", [])
            loc_candidate = locations[0] if locations else "Sector 1"

            geo = await disaster_geocoder.geocode_candidate(loc_candidate)
            lat = geo["latitude"] if geo else 19.0760
            lon = geo["longitude"] if geo else 72.8777

            severity = "HIGH" if "STRUCTURAL_COLLAPSE" in entities["severity_signals"] or "WATER_INUNDATION" in entities["severity_signals"] else "MEDIUM"

            alerts.append({
                "source": f"NEWS_WIRE ({source_name})",
                "disaster_type": disaster_type,
                "severity": severity,
                "title": f"News Wire: {headline[:60]}...",
                "description": headline,
                "latitude": lat,
                "longitude": lon,
                "confidence": round(cls_result["confidence"], 2),
                "matched_keywords": cls_result.get("keywords_detected", []),
                "extracted_entities": entities,
            })

        return alerts


emergency_news_feed = EmergencyNewsFeed()
