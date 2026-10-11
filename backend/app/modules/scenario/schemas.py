"""
AegisAI Scenario Module — Pydantic v2 Schemas.
Python 3.10 compatible.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.modules.scenario.enums import (
    DisasterSeverity,
    HospitalCapacityLevel,
    RiskLevel,
    WeatherPreset,
)

# --- Subsystem Configuration Schemas -----------------------------------------

class DisasterConfig(BaseModel):
    """Detailed hazard event configuration."""
    type: str = Field(
        default="EARTHQUAKE",
        description="Hazard type: EARTHQUAKE | FLOOD | FIRE | BUILDING_COLLAPSE | GAS_LEAK",
    )
    severity: DisasterSeverity = Field(default=DisasterSeverity.HIGH)
    latitude: float = Field(default=30.7333, ge=-90.0, le=90.0)
    longitude: float = Field(default=76.7794, ge=-180.0, le=180.0)
    radius_km: float = Field(default=5.0, ge=0.1, le=100.0)

    # Specific hazard attributes
    magnitude: float | None = Field(default=6.8, ge=1.0, le=10.0, description="Richter scale for earthquake")
    depth_km: float | None = Field(default=10.0, ge=1.0, le=700.0)
    rainfall_mm: float | None = Field(default=0.0, ge=0.0, le=1000.0)
    wind_speed_kmh: float | None = Field(default=15.0, ge=0.0, le=300.0)
    fuel_density: float | None = Field(default=1.0, ge=0.1, le=5.0)


class EnvironmentConfig(BaseModel):
    """Atmospheric and environmental parameters."""
    weather_preset: WeatherPreset = Field(default=WeatherPreset.CLEAR)
    temperature_celsius: float = Field(default=28.0, ge=-50.0, le=60.0)
    humidity_percent: float = Field(default=60.0, ge=0.0, le=100.0)
    rainfall_mm: float = Field(default=0.0, ge=0.0, le=500.0)
    wind_speed_kmh: float = Field(default=12.0, ge=0.0, le=250.0)
    wind_direction_deg: float = Field(default=180.0, ge=0.0, le=360.0)
    visibility_km: float = Field(default=10.0, ge=0.1, le=50.0)


class PopulationConfig(BaseModel):
    """Demographics and vulnerability parameters."""
    count: int = Field(default=50000, ge=100, le=10000000)
    density: str = Field(default="HIGH", pattern="^(LOW|MEDIUM|HIGH|VERY_HIGH)$")
    vulnerable_percentage: float = Field(default=15.0, ge=0.0, le=100.0)
    children_percentage: float = Field(default=18.0, ge=0.0, le=100.0)
    elderly_percentage: float = Field(default=12.0, ge=0.0, le=100.0)
    mobility_limited_percentage: float = Field(default=5.0, ge=0.0, le=100.0)


class ResourceConfig(BaseModel):
    """Emergency responder resource allocation."""
    ambulances: int = Field(default=12, ge=0, le=500)
    fire_trucks: int = Field(default=8, ge=0, le=500)
    police_units: int = Field(default=15, ge=0, le=500)
    rescue_teams: int = Field(default=10, ge=0, le=500)
    drones: int = Field(default=4, ge=0, le=100)
    helicopters: int = Field(default=2, ge=0, le=50)


class HospitalConfig(BaseModel):
    """Healthcare surge capacity overrides."""
    total_beds: int = Field(default=1400, ge=10)
    icu_beds: int = Field(default=180, ge=0)
    emergency_capacity_level: HospitalCapacityLevel = Field(default=HospitalCapacityLevel.NORMAL)
    staff_availability_percentage: float = Field(default=85.0, ge=10.0, le=100.0)
    medical_supplies_level: str = Field(default="ADEQUATE", pattern="^(SCARCE|ADEQUATE|SURPLUS)$")


class ShelterConfig(BaseModel):
    """Evacuation shelter network configuration."""
    capacity: int = Field(default=8000, ge=100)
    initial_occupancy: int = Field(default=500, ge=0)
    food_availability_days: int = Field(default=7, ge=1, le=60)
    water_availability_days: int = Field(default=7, ge=1, le=60)
    medical_support: bool = Field(default=True)


class InfrastructureConfig(BaseModel):
    """Lifeline infrastructure disruption levels."""
    road_damage_percentage: float = Field(default=15.0, ge=0.0, le=100.0)
    road_closure_percentage: float = Field(default=10.0, ge=0.0, le=100.0)
    bridge_damage_percentage: float = Field(default=5.0, ge=0.0, le=100.0)
    power_outage_percentage: float = Field(default=20.0, ge=0.0, le=100.0)
    water_disruption_percentage: float = Field(default=10.0, ge=0.0, le=100.0)
    communication_disruption_percentage: float = Field(default=15.0, ge=0.0, le=100.0)


class SimulationRunConfig(BaseModel):
    """Clock, duration, and reproducibility configuration."""
    duration_minutes: int = Field(default=60, ge=5, le=1440)
    speed: float = Field(default=1.0, ge=0.1, le=50.0)
    random_seed: int = Field(default=42, ge=0)


# --- Scenario CRUD & Action Schemas ------------------------------------------

class ScenarioCreateRequest(BaseModel):
    """Request payload to create a new Scenario."""
    name: str = Field(..., min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    disaster: DisasterConfig = Field(default_factory=DisasterConfig)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    population: PopulationConfig = Field(default_factory=PopulationConfig)
    resources: ResourceConfig = Field(default_factory=ResourceConfig)
    hospitals: HospitalConfig = Field(default_factory=HospitalConfig)
    shelters: ShelterConfig = Field(default_factory=ShelterConfig)
    infrastructure: InfrastructureConfig = Field(default_factory=InfrastructureConfig)
    simulation: SimulationRunConfig = Field(default_factory=SimulationRunConfig)
    is_template: bool = Field(default=False)


# Alias for backward compatibility
ScenarioCreate = ScenarioCreateRequest


class ScenarioUpdateRequest(BaseModel):
    """Partial update payload for a Scenario in DRAFT or READY state."""
    name: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    disaster: DisasterConfig | None = None
    environment: EnvironmentConfig | None = None
    population: PopulationConfig | None = None
    resources: ResourceConfig | None = None
    hospitals: HospitalConfig | None = None
    shelters: ShelterConfig | None = None
    infrastructure: InfrastructureConfig | None = None
    simulation: SimulationRunConfig | None = None
    is_template: bool | None = None


class ScenarioResponse(BaseModel):
    """Full Scenario Response."""
    id: str
    name: str
    description: str | None = None
    status: str
    created_by: int | None = None
    disaster_type: str
    severity: str
    latitude: float
    longitude: float
    radius_km: float
    population_count: int
    simulation_duration_minutes: int
    simulation_speed: float
    random_seed: int
    disaster_config: dict[str, Any]
    environment_config: dict[str, Any]
    population_config: dict[str, Any]
    resource_config: dict[str, Any]
    hospital_config: dict[str, Any]
    shelter_config: dict[str, Any]
    infrastructure_config: dict[str, Any]
    simulation_config: dict[str, Any]
    is_template: bool
    simulation_engine_version: str
    scenario_schema_version: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScenarioCloneRequest(BaseModel):
    """Request to duplicate an existing scenario for comparative analysis."""
    new_name: str | None = None
    description: str | None = None


# --- Validation & Preview Schemas --------------------------------------------

class ValidationErrorDetail(BaseModel):
    field: str
    message: str


class ScenarioValidateResponse(BaseModel):
    is_valid: bool
    message: str
    errors: list[ValidationErrorDetail] = Field(default_factory=list)


class ScenarioPreviewResponse(BaseModel):
    """Predictive baseline impact & risk preview."""
    scenario_name: str
    disaster_type: str
    severity: str
    epicenter: dict[str, float]
    radius_km: float
    affected_population: int
    estimated_casualties_low: int
    estimated_casualties_high: int
    estimated_evacuees: int
    hospital_demand_beds: int
    shelter_demand_beds: int
    resource_coverage_ratio: float
    baseline_risk_score: float
    risk_level: RiskLevel
    risk_factors: list[str]
    warnings: list[str]


# --- Scenario Run Schemas ----------------------------------------------------

class ScenarioRunResponse(BaseModel):
    """Scenario simulation run execution record."""
    id: str
    scenario_id: str
    status: str
    random_seed: int
    simulation_engine_version: str
    started_at: datetime
    ended_at: datetime | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    class Config:
        from_attributes = True


class PresetResponse(BaseModel):
    """Preset scenario template metadata."""
    preset_id: str
    name: str
    description: str
    disaster_type: str
    severity: str
    icon: str
    configuration: ScenarioCreateRequest
