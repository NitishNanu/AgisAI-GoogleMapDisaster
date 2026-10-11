"""
AegisAI Scenario Module — Enums and Types.
Python 3.10 compatible.
"""

from enum import Enum


class ScenarioStatus(str, Enum):
    """Lifecycle states of a disaster scenario."""
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class ScenarioRunStatus(str, Enum):
    """Execution states of a scenario simulation run."""
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DisasterSeverity(str, Enum):
    """Standardized disaster severity classification."""
    LOW = "LOW"
    MODERATE = "MODERATE"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"


class WeatherPreset(str, Enum):
    """Predefined atmospheric conditions."""
    CLEAR = "CLEAR"
    RAIN = "RAIN"
    HEAVY_RAIN = "HEAVY_RAIN"
    STORM = "STORM"
    HIGH_WIND = "HIGH_WIND"
    EXTREME_HEAT = "EXTREME_HEAT"


class HospitalCapacityLevel(str, Enum):
    """Hospital surge status."""
    NORMAL = "NORMAL"
    REDUCED = "REDUCED"
    OVERLOADED = "OVERLOADED"


class RiskLevel(str, Enum):
    """Baseline risk assessment level."""
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"
