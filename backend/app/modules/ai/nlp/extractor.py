"""
AegisAI / RescueNet AI — Emergency Named Entity Extractor (Level 3).

Extracts key operational emergency entities from unstructured text:
- LOCATION / ROAD / LANDMARK
- CASUALTIES / INJURIES / TRAPPED
- DISASTER_TYPE
- INFRASTRUCTURE / UTILITIES
- TIME / FRESHNESS
"""

import re
from typing import Any

LOCATION_PATTERNS = [
    r"(?:near|at|around|close to|on|along|by|in)\s+([A-Z0-9][a-zA-Z0-9\s\.\,\-]+?(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Sector\s+\d+|Zone\s+[A-Z\d]+|Highway|Bridge|Square|Park|Hospital|Station|Center))",
    r"(?:Sector\s+\d+|Zone\s+[A-Z\d]+|Block\s+[A-Z\d]+)",
    r"(?:Downtown|Uptown|Midtown|North\s+Side|South\s+District|West\s+End|East\s+Bay)",
]

CASUALTY_PATTERNS = [
    r"(\d+)\s+(?:people|persons|victims|casualties|citizens|civilians)\s+(?:trapped|injured|dead|hurt|buried|stranded)",
    r"(?:trapped|injured|buried|stranded)\s+(\d+)\s+(?:people|persons|victims)",
    r"(?:multiple|several)\s+(?:casualties|people\s+trapped|victims)",
]

INFRASTRUCTURE_PATTERNS = [
    r"(?:hospital|bridge|power\s+station|water\s+plant|communication\s+tower|school|freeway|subway|tunnel|warehouse)",
]


class EmergencyEntityExtractor:
    """
    Rule-based and heuristic NER system for emergency dispatches.
    """

    @staticmethod
    def extract_entities(text: str) -> dict[str, Any]:
        """
        Extracts structured entities from emergency report string.
        """
        if not text:
            return {
                "locations": [],
                "casualties": None,
                "trapped_count": 0,
                "infrastructure": [],
                "severity_signals": [],
            }

        locations = []
        for pattern in LOCATION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                cleaned = m.strip(" .,-") if isinstance(m, str) else m
                if cleaned and len(cleaned) > 2 and cleaned not in locations:
                    locations.append(cleaned)

        casualties = 0
        trapped = 0
        for pattern in CASUALTY_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                if isinstance(m, str) and m.isdigit():
                    casualties += int(m)
                    trapped += int(m)

        infrastructure = []
        for pattern in INFRASTRUCTURE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                if m.lower() not in [item.lower() for item in infrastructure]:
                    infrastructure.append(m.capitalize())

        # Detect severity signals
        severity_signals = []
        lower = text.lower()
        if any(w in lower for w in ["submerged", "underwater", "flooding", "water level rising"]):
            severity_signals.append("WATER_INUNDATION")
        if any(w in lower for w in ["fire", "blaze", "heavy smoke", "flames"]):
            severity_signals.append("ACTIVE_FIRE")
        if any(w in lower for w in ["collapsed", "debris", "roof fell", "rubble"]):
            severity_signals.append("STRUCTURAL_COLLAPSE")
        if any(w in lower for w in ["trapped", "screaming", "cannot escape"]):
            severity_signals.append("IMMINENT_HUMAN_PERIL")

        return {
            "locations": locations,
            "estimated_casualties": casualties,
            "trapped_count": trapped,
            "infrastructure_affected": infrastructure,
            "severity_signals": severity_signals,
        }


emergency_entity_extractor = EmergencyEntityExtractor()
