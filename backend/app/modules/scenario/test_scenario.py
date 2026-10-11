"""
AegisAI Scenario Module — Unit & Integration Tests.
Verifies ScenarioValidator, BaselineRiskScorer, Presets, and domain lifecycle.
Python 3.10 compatible.
"""

from app.modules.scenario.enums import DisasterSeverity, RiskLevel, WeatherPreset
from app.modules.scenario.presets import get_scenario_presets
from app.modules.scenario.risk_scorer import BaselineRiskScorer
from app.modules.scenario.schemas import (
    DisasterConfig,
    EnvironmentConfig,
    HospitalConfig,
    InfrastructureConfig,
    PopulationConfig,
    ResourceConfig,
    ScenarioCreateRequest,
    ShelterConfig,
    SimulationRunConfig,
)
from app.modules.scenario.validator import ScenarioValidator


def test_scenario_validator_valid_payload():
    """Verify that a standard scenario configuration passes validation."""
    payload = ScenarioCreateRequest(
        name="Test Valid Earthquake Scenario",
        description="Testing validator boundary checks",
        disaster=DisasterConfig(
            type="EARTHQUAKE",
            severity=DisasterSeverity.HIGH,
            latitude=30.7333,
            longitude=76.7794,
            radius_km=5.0,
        ),
        environment=EnvironmentConfig(
            weather_preset=WeatherPreset.CLEAR,
            temperature_celsius=25.0,
        ),
        population=PopulationConfig(
            count=50000,
            density="HIGH",
            vulnerable_percentage=12.0,
        ),
        resources=ResourceConfig(
            ambulances=10,
            fire_trucks=5,
            rescue_teams=8,
        ),
        hospitals=HospitalConfig(
            total_beds=1000,
            icu_beds=100,
        ),
        shelters=ShelterConfig(
            capacity=5000,
            initial_occupancy=200,
        ),
        infrastructure=InfrastructureConfig(
            road_damage_percentage=15.0,
        ),
        simulation=SimulationRunConfig(
            duration_minutes=60,
            speed=2.0,
            random_seed=42,
        ),
    )

    result = ScenarioValidator.validate(payload)
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_scenario_validator_invalid_boundaries():
    """Verify that invalid coordinates, negative resources, and duration are caught."""
    payload = ScenarioCreateRequest.model_construct(
        name="Invalid Scenario",
        disaster=DisasterConfig.model_construct(
            type="INVALID_DISASTER_TYPE",
            severity=DisasterSeverity.HIGH,
            latitude=999.0,  # Invalid lat
            longitude=-200.0,  # Invalid lon
            radius_km=-5.0,  # Invalid radius
        ),
        population=PopulationConfig.model_construct(
            count=-100,  # Invalid count
            vulnerable_percentage=150.0,
        ),
        resources=ResourceConfig.model_construct(
            ambulances=-5,  # Invalid resource
            fire_trucks=0,
            police_units=0,
            rescue_teams=0,
            drones=0,
            helicopters=0,
        ),
        hospitals=HospitalConfig.model_construct(
            total_beds=100,
            icu_beds=200,  # ICU exceeds total beds
        ),
        shelters=ShelterConfig.model_construct(
            capacity=1000,
            initial_occupancy=2000,
        ),
        infrastructure=InfrastructureConfig.model_construct(),
        environment=EnvironmentConfig.model_construct(),
        simulation=SimulationRunConfig.model_construct(
            duration_minutes=2000,  # Exceeds max 1440 min
            speed=-1.0,  # Invalid speed
        ),
    )

    result = ScenarioValidator.validate(payload)
    assert result.is_valid is False
    assert len(result.errors) >= 5
    error_fields = [e.field for e in result.errors]
    assert "disaster.type" in error_fields
    assert "disaster.latitude" in error_fields
    assert "disaster.longitude" in error_fields
    assert "population.count" in error_fields
    assert "resources" in error_fields
    assert "hospitals.icu_beds" in error_fields
    assert "simulation.duration_minutes" in error_fields


def test_baseline_risk_scorer():
    """Verify deterministic multi-factor risk score calculation."""
    payload = ScenarioCreateRequest(
        name="Critical Seismic Scenario",
        disaster=DisasterConfig(
            type="EARTHQUAKE",
            severity=DisasterSeverity.CRITICAL,
            latitude=30.7399,
            longitude=76.7830,
            radius_km=10.0,
        ),
        population=PopulationConfig(
            count=150000,
            density="VERY_HIGH",
            vulnerable_percentage=25.0,
        ),
        resources=ResourceConfig(
            ambulances=4,  # Severe deficit
            fire_trucks=2,
            rescue_teams=2,
        ),
        hospitals=HospitalConfig(
            total_beds=500,
            icu_beds=50,
        ),
        infrastructure=InfrastructureConfig(
            road_damage_percentage=50.0,
            power_outage_percentage=60.0,
        ),
    )

    preview = BaselineRiskScorer.calculate_preview(payload)
    assert preview.baseline_risk_score >= 70.0
    assert preview.risk_level in (RiskLevel.SEVERE, RiskLevel.CRITICAL)
    assert preview.estimated_casualties_high > 0
    assert len(preview.risk_factors) >= 3
    assert preview.resource_coverage_ratio < 1.0


def test_presets_catalog():
    """Verify built-in presets catalog loads cleanly and all presets are valid."""
    presets = get_scenario_presets()
    assert len(presets) >= 3
    for p in presets:
        val = ScenarioValidator.validate(p.configuration)
        assert val.is_valid is True, f"Preset '{p.name}' failed validation: {val.errors}"
