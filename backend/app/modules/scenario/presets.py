"""
AegisAI Scenario Module — Built-in Standardized Scenario Presets.
Python 3.10 compatible.
"""


from app.modules.scenario.enums import DisasterSeverity, HospitalCapacityLevel, WeatherPreset
from app.modules.scenario.schemas import (
    DisasterConfig,
    EnvironmentConfig,
    HospitalConfig,
    InfrastructureConfig,
    PopulationConfig,
    PresetResponse,
    ResourceConfig,
    ScenarioCreateRequest,
    ShelterConfig,
    SimulationRunConfig,
)


def get_scenario_presets() -> list[PresetResponse]:
    """Return catalog of standardized, ready-to-run scenario blueprints."""
    return [
        PresetResponse(
            preset_id="preset_urban_earthquake",
            name="Major Urban Earthquake (M7.2)",
            description="High-magnitude tectonic rupture affecting commercial core with structural collapse and road blockage.",
            disaster_type="EARTHQUAKE",
            severity="SEVERE",
            icon="🌋",
            configuration=ScenarioCreateRequest(
                name="Major Urban Earthquake (M7.2)",
                description="Simulated 7.2 Richter earthquake impacting Sector 17 commercial zone with moderate building damage.",
                disaster=DisasterConfig(
                    type="EARTHQUAKE",
                    severity=DisasterSeverity.SEVERE,
                    latitude=30.7399,
                    longitude=76.7830,
                    radius_km=6.0,
                    magnitude=7.2,
                    depth_km=12.0,
                ),
                environment=EnvironmentConfig(
                    weather_preset=WeatherPreset.CLEAR,
                    temperature_celsius=26.0,
                    wind_speed_kmh=10.0,
                ),
                population=PopulationConfig(
                    count=85000,
                    density="HIGH",
                    vulnerable_percentage=14.0,
                ),
                resources=ResourceConfig(
                    ambulances=14,
                    fire_trucks=10,
                    police_units=18,
                    rescue_teams=12,
                    drones=6,
                    helicopters=2,
                ),
                hospitals=HospitalConfig(
                    total_beds=1600,
                    icu_beds=220,
                    emergency_capacity_level=HospitalCapacityLevel.NORMAL,
                ),
                shelters=ShelterConfig(
                    capacity=10000,
                    initial_occupancy=400,
                ),
                infrastructure=InfrastructureConfig(
                    road_damage_percentage=25.0,
                    road_closure_percentage=15.0,
                    bridge_damage_percentage=10.0,
                    power_outage_percentage=35.0,
                ),
                simulation=SimulationRunConfig(
                    duration_minutes=90,
                    speed=2.0,
                    random_seed=101,
                ),
            ),
        ),
        PresetResponse(
            preset_id="preset_monsoon_flood",
            name="Monsoon Flash Flood Inundation",
            description="Torrential rainfall causing river overflow, waterlogged arterial corridors, and mass evacuations.",
            disaster_type="FLOOD",
            severity="HIGH",
            icon="🌊",
            configuration=ScenarioCreateRequest(
                name="Monsoon Flash Flood Inundation",
                description="Heavy continuous precipitation causing regional flooding and shelter surge.",
                disaster=DisasterConfig(
                    type="FLOOD",
                    severity=DisasterSeverity.HIGH,
                    latitude=30.7150,
                    longitude=76.7600,
                    radius_km=4.5,
                    rainfall_mm=120.0,
                ),
                environment=EnvironmentConfig(
                    weather_preset=WeatherPreset.HEAVY_RAIN,
                    temperature_celsius=22.0,
                    humidity_percent=95.0,
                    rainfall_mm=120.0,
                    wind_speed_kmh=35.0,
                    visibility_km=3.0,
                ),
                population=PopulationConfig(
                    count=45000,
                    density="MEDIUM",
                    vulnerable_percentage=18.0,
                ),
                resources=ResourceConfig(
                    ambulances=8,
                    fire_trucks=6,
                    police_units=12,
                    rescue_teams=16,
                    drones=8,
                    helicopters=3,
                ),
                hospitals=HospitalConfig(
                    total_beds=1200,
                    icu_beds=140,
                ),
                shelters=ShelterConfig(
                    capacity=12000,
                    initial_occupancy=1200,
                ),
                infrastructure=InfrastructureConfig(
                    road_damage_percentage=35.0,
                    road_closure_percentage=40.0,
                    water_disruption_percentage=45.0,
                    power_outage_percentage=25.0,
                ),
                simulation=SimulationRunConfig(
                    duration_minutes=60,
                    speed=2.0,
                    random_seed=202,
                ),
            ),
        ),
        PresetResponse(
            preset_id="preset_industrial_fire",
            name="Industrial Chemical Fire & Hazmat",
            description="Major chemical facility blaze with toxic plume dispersion requiring immediate downwind evacuation.",
            disaster_type="FIRE",
            severity="CRITICAL",
            icon="🔥",
            configuration=ScenarioCreateRequest(
                name="Industrial Chemical Fire & Hazmat",
                description="High-temperature structural chemical fire with gas dispersion.",
                disaster=DisasterConfig(
                    type="FIRE",
                    severity=DisasterSeverity.CRITICAL,
                    latitude=30.7150,
                    longitude=76.7600,
                    radius_km=3.5,
                    fuel_density=3.5,
                    wind_speed_kmh=28.0,
                ),
                environment=EnvironmentConfig(
                    weather_preset=WeatherPreset.HIGH_WIND,
                    temperature_celsius=36.0,
                    humidity_percent=30.0,
                    wind_speed_kmh=28.0,
                    wind_direction_deg=225.0,
                ),
                population=PopulationConfig(
                    count=30000,
                    density="MEDIUM",
                    vulnerable_percentage=12.0,
                ),
                resources=ResourceConfig(
                    ambulances=15,
                    fire_trucks=18,
                    police_units=10,
                    rescue_teams=10,
                    drones=6,
                ),
                hospitals=HospitalConfig(
                    total_beds=1400,
                    icu_beds=180,
                    emergency_capacity_level=HospitalCapacityLevel.REDUCED,
                ),
                shelters=ShelterConfig(
                    capacity=6000,
                    initial_occupancy=200,
                ),
                infrastructure=InfrastructureConfig(
                    road_damage_percentage=10.0,
                    road_closure_percentage=25.0,
                    power_outage_percentage=15.0,
                ),
                simulation=SimulationRunConfig(
                    duration_minutes=45,
                    speed=1.0,
                    random_seed=303,
                ),
            ),
        ),
    ]
