"""
AegisAI AI Agents Module — Pydantic Schemas.

Defines the request and response models for:
- Incident Intelligence & Action Plan Agent
- Mission Operations & In-Flight Dispatch Agent
- Scenario Architect & Blueprint Generator Agent
"""

from typing import Any

from pydantic import BaseModel, Field

# ============================================================================
# INCIDENT INTELLIGENCE AGENT SCHEMAS
# ============================================================================

class IncidentTriageRequest(BaseModel):
    incident_id: int
    weather_override: str | None = None
    population_density: str | None = None  # LOW, MEDIUM, HIGH, DENSE


class HazardZoneEnvelope(BaseModel):
    horizon_minutes: int
    radius_meters: float
    area_sq_km: float
    threat_level: str  # RED_EVACUATE, ORANGE_SHELTER, YELLOW_ADVISORY
    wind_adjusted_bearing_deg: float
    polygon_coordinates: list[list[float]] = Field(default_factory=list)


class TacticalObjective(BaseModel):
    id: str
    phase: str  # IMMEDIATE, STABILIZATION, CONTAINMENT, RECOVERY
    objective: str
    assigned_unit_type: str
    target_time_minutes: int
    priority: str  # CRITICAL, HIGH, MEDIUM


class SecondaryCascadeRisk(BaseModel):
    hazard_type: str
    probability_pct: float
    trigger_condition: str
    mitigation_action: str


class IncidentActionPlan(BaseModel):
    incident_id: int
    incident_title: str
    severity: str
    disaster_type: str
    commander_summary: str
    estimated_casualties: int
    critical_patients: int
    containment_status_pct: float
    safety_perimeter_meters: float
    evacuation_radius_meters: float
    staging_area: dict[str, Any]
    required_resources: dict[str, int]
    tactical_objectives: list[TacticalObjective]
    cascade_risks: list[SecondaryCascadeRisk]
    hazard_envelopes: list[HazardZoneEnvelope]
    reasoning_steps: list[str] = Field(default_factory=list)
    generated_at: str


class HazardEnvelopeResponse(BaseModel):
    incident_id: int
    center_latitude: float
    center_longitude: float
    current_radius_meters: float
    wind_direction_deg: float
    wind_speed_kmh: float
    envelopes: list[HazardZoneEnvelope]
    evacuation_zone_area_sq_km: float
    estimated_endangered_population: int


# ============================================================================
# MISSION OPERATIONS AGENT SCHEMAS
# ============================================================================

class MissionTelemetryAnomaly(BaseModel):
    anomaly_type: str  # STALLED_PROGRESS, ROUTE_CONGESTION, CASUALTY_SURGE, CAPACITY_OVERFLOW
    severity: str  # CRITICAL, HIGH, WARNING
    description: str
    recommended_action: str


class HospitalMedevacCandidate(BaseModel):
    hospital_id: int
    hospital_name: str
    distance_km: float
    eta_minutes: float
    available_beds: int
    icu_beds_available: int
    trauma_level: str
    suitability_score: float
    route_geometry: list[list[float]] | None = None
    is_recommended: bool = False


class MissionMedevacRecommendation(BaseModel):
    assignment_id: int
    incident_id: int
    current_team_id: int
    selected_hospital: HospitalMedevacCandidate
    alternative_hospitals: list[HospitalMedevacCandidate]
    triage_notes: str
    critical_patients_count: int


class MissionSITREP(BaseModel):
    assignment_id: int
    incident_id: int
    incident_title: str
    team_name: str
    vehicle_type: str
    current_status: str
    elapsed_minutes: float
    distance_remaining_km: float
    eta_remaining_minutes: float
    operational_milestones: list[str]
    casualties_handled: int
    critical_triage_count: int
    anomalies: list[MissionTelemetryAnomaly]
    tactical_next_steps: list[str]
    backup_recommended: bool
    recommended_backup_type: str | None = None
    reasoning_steps: list[str] = Field(default_factory=list)
    generated_at: str


class MissionMonitorReport(BaseModel):
    total_active_missions: int
    on_schedule_count: int
    delayed_count: int
    critical_alerts_count: int
    mission_sitreps: list[MissionSITREP]
    system_load_status: str


# ============================================================================
# SCENARIO ARCHITECT AGENT SCHEMAS
# ============================================================================

class ScenarioPromptGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=10, description="Natural language disaster description")
    region_name: str | None = "Chandigarh Urban Metropolitan"
    difficulty_level: str = "MODERATE"  # LOW, MODERATE, SEVERE, CATASTROPHIC


class ScenarioInjectEvent(BaseModel):
    minute_mark: int
    event_type: str  # SECONDARY_HAZARD, INFRASTRUCTURE_FAILURE, CASUALTY_SURGE, WEATHER_SHIFT
    title: str
    description: str
    impact_description: str
    affected_radius_multiplier: float = 1.0
    additional_casualties: int = 0


class ScenarioStressTestResult(BaseModel):
    scenario_id: str | None = None
    scenario_name: str
    difficulty_rating: str
    preparedness_score: float  # 0 to 100
    peak_casualty_minute: int
    projected_total_casualties: int
    icu_saturation_minute: int | None
    fleet_exhaustion_minute: int | None
    primary_bottleneck: str
    mitigation_recommendations: list[str]
    cascading_timeline: list[ScenarioInjectEvent]
    simulation_curve: list[dict[str, Any]]
