"""
AegisAI / RescueNet AI — Ollama Structured JSON NLP Extractor (Level 4).

Extracts disaster report metadata with strict schema validation and fallback:
{
  "disaster_type": "flood",
  "location_candidates": [{"text": "Sector 17", "confidence": 0.91}],
  "severity_indicators": ["roads submerged", "vehicles stranded"],
  "summary": "Flooding reported around Sector 17."
}
"""

import json
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.modules.ai.nlp.classifier import disaster_nlp_classifier
from app.modules.ai.nlp.extractor import emergency_entity_extractor
from app.modules.ai.providers.ollama_provider import ollama_provider

logger = structlog.get_logger("aegis_ai.nlp.ollama_extractor")


class DisasterReportExtraction(BaseModel):
    disaster_type: str = Field(..., description="Class of disaster (flood, fire, earthquake, etc.)")
    location_candidates: list[dict] = Field(default_factory=list)
    severity_indicators: list[str] = Field(default_factory=list)
    estimated_casualties: int = Field(default=0)
    summary: str = Field(..., description="Concise operational summary")


class OllamaDisasterExtractor:
    """
    Combines LLM structured extraction with classical NLP fallback to guarantee production availability.
    """

    @staticmethod
    async def extract_and_validate(text: str) -> dict[str, Any]:
        """
        Attempts structured JSON extraction via Ollama, falling back to rule-based NLP if Ollama is unavailable.
        """
        prompt = (
            "You are an Emergency Dispatch AI System. Extract structured JSON metadata from the following disaster report.\n"
            "Format MUST strictly follow this JSON schema:\n"
            "{\n"
            '  "disaster_type": "FLOOD | FIRE | EARTHQUAKE | LANDSLIDE | CYCLONE | BUILDING_COLLAPSE | ROAD_ACCIDENT | INDUSTRIAL_ACCIDENT | OTHER",\n'
            '  "location_candidates": [{"text": "name", "confidence": 0.0-1.0}],\n'
            '  "severity_indicators": ["indicator1", "indicator2"],\n'
            '  "estimated_casualties": 0,\n'
            '  "summary": "Brief 1-line tactical summary"\n'
            "}\n\n"
            f"REPORT:\n\"{text}\"\n\nJSON Output:"
        )

        try:
            raw_response = await ollama_provider.generate(prompt=prompt, system_prompt="Output ONLY valid JSON.")
            if raw_response and raw_response.strip():
                # Attempt to parse json
                cleaned = raw_response.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

                parsed = json.loads(cleaned)
                validated = DisasterReportExtraction(**parsed)
                return {
                    "source": "OLLAMA_QWEN",
                    "data": validated.model_dump(),
                    "status": "VALIDATED",
                }
        except Exception as e:
            logger.warning("ollama_nlp_extraction_failed_using_baseline_fallback", error=str(e))

        # Fallback to deterministic Level 1 & Level 3 NLP pipeline
        cls_result = disaster_nlp_classifier.predict(text)
        entities = emergency_entity_extractor.extract_entities(text)

        locations = [{"text": loc, "confidence": 0.85} for loc in entities["locations"]]
        fallback_data = DisasterReportExtraction(
            disaster_type=cls_result["predicted_class"],
            location_candidates=locations,
            severity_indicators=entities["severity_signals"],
            estimated_casualties=entities["estimated_casualties"],
            summary=f"{cls_result['predicted_class']} event reported. Affected: {', '.join(entities['infrastructure_affected']) if entities['infrastructure_affected'] else 'General Sector'}.",
        )

        return {
            "source": "DETERMINISTIC_NLP_FALLBACK",
            "data": fallback_data.model_dump(),
            "status": "VALIDATED",
        }


ollama_disaster_extractor = OllamaDisasterExtractor()
