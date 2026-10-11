"""
AegisAI Scenario Module — Dedicated Scenario Validator.
Performs semantic boundary checks, geographic sanity validation, and resource consistency rules.
Python 3.10 compatible.
"""


from app.modules.scenario.schemas import (
    ScenarioCreateRequest,
    ScenarioValidateResponse,
    ValidationErrorDetail,
)

VALID_DISASTER_TYPES = {
    "EARTHQUAKE",
    "FLOOD",
    "FIRE",
    "BUILDING_COLLAPSE",
    "GAS_LEAK",
    "HAZMAT",
    "CYCLONE",
    "STORM",
    "TSUNAMI",
    "HURRICANE",
    "PANDEMIC",
    "ACCIDENT",
    "WILDFIRE",
    "LANDSLIDE",
}


class ScenarioValidator:
    """Enterprise validator for disaster simulation blueprints."""

    @classmethod
    def validate(cls, payload: ScenarioCreateRequest) -> ScenarioValidateResponse:
        errors: list[ValidationErrorDetail] = []

        # 1. Disaster Configuration Validation
        disaster = payload.disaster
        dtype = disaster.type.upper() if disaster.type else ""
        if dtype not in VALID_DISASTER_TYPES:
            errors.append(
                ValidationErrorDetail(
                    field="disaster.type",
                    message=f"Disaster type '{disaster.type}' is invalid. Supported: {', '.join(sorted(VALID_DISASTER_TYPES))}",
                )
            )

        if not (-90.0 <= disaster.latitude <= 90.0):
            errors.append(
                ValidationErrorDetail(
                    field="disaster.latitude",
                    message="Latitude must be between -90.0 and 90.0 degrees.",
                )
            )

        if not (-180.0 <= disaster.longitude <= 180.0):
            errors.append(
                ValidationErrorDetail(
                    field="disaster.longitude",
                    message="Longitude must be between -180.0 and 180.0 degrees.",
                )
            )

        if disaster.radius_km <= 0.0 or disaster.radius_km > 100.0:
            errors.append(
                ValidationErrorDetail(
                    field="disaster.radius_km",
                    message="Affected radius must be between 0.1 and 100.0 km.",
                )
            )

        # 2. Population Validation
        pop = payload.population
        if pop.count <= 0:
            errors.append(
                ValidationErrorDetail(
                    field="population.count",
                    message="Total population must be greater than zero.",
                )
            )

        if pop.vulnerable_percentage < 0.0 or pop.vulnerable_percentage > 100.0:
            errors.append(
                ValidationErrorDetail(
                    field="population.vulnerable_percentage",
                    message="Vulnerable percentage must be between 0.0 and 100.0%.",
                )
            )

        # 3. Resources Validation
        res = payload.resources
        if any(val < 0 for val in [res.ambulances, res.fire_trucks, res.police_units, res.rescue_teams, res.drones, res.helicopters]):
            errors.append(
                ValidationErrorDetail(
                    field="resources",
                    message="All emergency resource quantities must be non-negative integers.",
                )
            )

        # 4. Hospital & Shelter Capacity Validation
        hosp = payload.hospitals
        if hosp.total_beds <= 0:
            errors.append(
                ValidationErrorDetail(
                    field="hospitals.total_beds",
                    message="Total hospital beds must be greater than zero.",
                )
            )
        if hosp.icu_beds > hosp.total_beds:
            errors.append(
                ValidationErrorDetail(
                    field="hospitals.icu_beds",
                    message="ICU beds cannot exceed total available hospital beds.",
                )
            )

        shelter = payload.shelters
        if shelter.capacity <= 0:
            errors.append(
                ValidationErrorDetail(
                    field="shelters.capacity",
                    message="Shelter capacity must be greater than zero.",
                )
            )
        if shelter.initial_occupancy > shelter.capacity:
            errors.append(
                ValidationErrorDetail(
                    field="shelters.initial_occupancy",
                    message="Initial shelter occupancy cannot exceed total capacity.",
                )
            )

        # 5. Simulation Duration & Speed Validation
        sim = payload.simulation
        if sim.duration_minutes < 5 or sim.duration_minutes > 1440:
            errors.append(
                ValidationErrorDetail(
                    field="simulation.duration_minutes",
                    message="Simulation duration must be between 5 minutes and 1440 minutes (24 hours).",
                )
            )
        if sim.speed < 0.1 or sim.speed > 50.0:
            errors.append(
                ValidationErrorDetail(
                    field="simulation.speed",
                    message="Simulation clock speed multiplier must be between 0.1x and 50.0x.",
                )
            )

        is_valid = len(errors) == 0
        message = "Scenario configuration is valid." if is_valid else f"Validation failed with {len(errors)} error(s)."

        return ScenarioValidateResponse(
            is_valid=is_valid,
            message=message,
            errors=errors,
        )
