"""
Tests for NLP text classification, NER, Geocoding, Computer Vision, and Dynamic Routing.
"""

from app.modules.ai.nlp.classifier import disaster_nlp_classifier
from app.modules.ai.nlp.extractor import emergency_entity_extractor
from app.modules.ai.nlp.geocoder import disaster_geocoder
from app.modules.ai.vision.service import cv_analyzer
from app.routing.hazard_router import hazard_router


def test_disaster_nlp_classifier_flood():
    text = "Heavy rainfall causing river overflow and submerged roads in downtown"
    result = disaster_nlp_classifier.predict(text)
    assert result["predicted_class"] == "FLOOD"
    assert result["confidence"] > 0.0
    assert "flood" in result["class_probabilities"] or "FLOOD" in result["class_probabilities"]


def test_disaster_nlp_classifier_fire():
    text = "Massive structural fire with thick black smoke coming from factory"
    result = disaster_nlp_classifier.predict(text)
    assert result["predicted_class"] in ["FIRE", "INDUSTRIAL_ACCIDENT"]
    assert result["confidence"] > 0.0


def test_emergency_entity_extractor():
    text = "Severe building collapse at Sector 14 near City Hospital. 5 people trapped under debris."
    entities = emergency_entity_extractor.extract_entities(text)
    assert len(entities["locations"]) > 0
    assert entities["trapped_count"] == 5
    assert "STRUCTURAL_COLLAPSE" in entities["severity_signals"]
    assert "Hospital" in entities["infrastructure_affected"] or "Hospital" in str(entities["locations"])


def test_disaster_geocoder_synthetic_zone():
    import asyncio
    geo = asyncio.run(disaster_geocoder.geocode_candidate("Sector 12"))
    assert geo is not None
    assert geo["confidence"] >= 0.90
    assert 18.0 <= geo["latitude"] <= 21.0
    assert 72.0 <= geo["longitude"] <= 75.0


def test_computer_vision_analyzer():
    result = cv_analyzer.analyze_image_bytes(b"dummy_image_data", filename="flood_water_street.jpg")
    assert result["primary_hazard"] == "flood"
    assert result["confidence"] > 0.8
    assert len(result["detected_objects"]) > 0


def test_dynamic_hazard_router():
    hazard_router.clear_hazards()
    hazard_router.register_hazard(lat=19.08, lon=72.88, hazard_type="ROAD_BLOCK", radius_km=1.0)

    route = hazard_router.calculate_safe_route(
        start_lat=19.07,
        start_lon=72.87,
        end_lat=19.09,
        end_lon=72.89,
        avoid_hazards=True,
    )
    assert route["distance_km"] > 0
    assert route["duration_minutes"] > 0
    assert route["safety_score"] <= 1.0
    assert "geometry" in route
