"""
AegisAI Scenario Module — Baseline Risk Scorer & Impact Estimator.
Transparent deterministic analytical model estimating casualty ranges, bed pressure, and risk score.
Python 3.10 compatible.
"""


from app.modules.scenario.enums import DisasterSeverity, RiskLevel
from app.modules.scenario.schemas import ScenarioCreateRequest, ScenarioPreviewResponse


class BaselineRiskScorer:
    """Multi-factor baseline risk scoring engine."""

    SEVERITY_WEIGHTS = {
        DisasterSeverity.LOW: 0.2,
        DisasterSeverity.MODERATE: 0.4,
        DisasterSeverity.MEDIUM: 0.4,
        DisasterSeverity.HIGH: 0.7,
        DisasterSeverity.SEVERE: 0.85,
        DisasterSeverity.CRITICAL: 1.0,
    }

    @classmethod
    def calculate_preview(cls, scenario: ScenarioCreateRequest) -> ScenarioPreviewResponse:
        disaster = scenario.disaster
        pop = scenario.population
        infra = scenario.infrastructure
        res = scenario.resources
        hosp = scenario.hospitals
        shelter = scenario.shelters

        # 1. Calculate Estimated Affected Population within Radius
        area_sq_km = 3.14159 * (disaster.radius_km ** 2)
        density_factor = 1.5 if pop.density == "VERY_HIGH" else (1.2 if pop.density == "HIGH" else (0.8 if pop.density == "MEDIUM" else 0.5))
        # Estimate affected population capped at total population
        affected_pop = min(pop.count, max(100, int(area_sq_km * 800 * density_factor)))

        # 2. Severity Factor
        sev_weight = cls.SEVERITY_WEIGHTS.get(disaster.severity, 0.7)

        # 3. Estimated Casualties & Evacuees
        vulnerable_factor = 1.0 + (pop.vulnerable_percentage / 100.0) * 0.5
        casualty_rate_low = 0.002 * sev_weight * vulnerable_factor
        casualty_rate_high = 0.015 * sev_weight * vulnerable_factor

        cas_low = max(0, int(affected_pop * casualty_rate_low))
        cas_high = max(cas_low + 1, int(affected_pop * casualty_rate_high))
        evacuees = int(affected_pop * (0.15 + 0.35 * sev_weight))

        # 4. Hospital & Shelter Demand
        hospital_demand = int(cas_high * 1.8)
        shelter_demand = int(evacuees * 0.6)

        # 5. Emergency Resource Coverage Ratio
        total_field_units = res.ambulances + res.fire_trucks + res.rescue_teams
        units_needed = max(1, affected_pop // 2000)
        resource_coverage = round(min(2.0, total_field_units / units_needed), 2)

        # 6. Composite Risk Score (0 - 100)
        infra_penalty = (
            infra.road_damage_percentage * 0.2
            + infra.bridge_damage_percentage * 0.15
            + infra.power_outage_percentage * 0.1
        )
        hosp_stress_penalty = max(0.0, (hospital_demand - hosp.total_beds) / max(1, hosp.total_beds) * 30.0)
        resource_deficit_penalty = max(0.0, (1.0 - resource_coverage) * 25.0)

        raw_score = (sev_weight * 40.0) + (infra_penalty * 0.25) + hosp_stress_penalty + resource_deficit_penalty
        risk_score = round(max(5.0, min(99.0, raw_score)), 1)

        # Determine Risk Level
        if risk_score >= 80.0:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 65.0:
            risk_level = RiskLevel.SEVERE
        elif risk_score >= 45.0:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 25.0:
            risk_level = RiskLevel.MODERATE
        else:
            risk_level = RiskLevel.LOW

        # Generate Explainable Risk Factors
        risk_factors: list[str] = []
        if sev_weight >= 0.7:
            risk_factors.append(f"Elevated hazard severity level ({disaster.severity.value})")
        if affected_pop > 10000:
            risk_factors.append(f"High population exposure ({affected_pop:,} residents in impact zone)")
        if infra.road_damage_percentage >= 20.0:
            risk_factors.append(f"Substantial road network disruption ({infra.road_damage_percentage:.0f}% damaged)")
        if resource_coverage < 0.8:
            risk_factors.append(f"Response fleet deficit (Coverage ratio {resource_coverage}x below nominal)")
        if hospital_demand > hosp.total_beds * 0.8:
            risk_factors.append("Severe surge pressure on regional trauma & emergency beds")
        if pop.vulnerable_percentage >= 15.0:
            risk_factors.append(f"High vulnerable demographic proportion ({pop.vulnerable_percentage:.0f}%)")

        warnings: list[str] = []
        if hospital_demand > hosp.total_beds:
            warnings.append(f"Hospital bed demand ({hospital_demand}) exceeds total regional capacity ({hosp.total_beds})!")
        if shelter_demand > shelter.capacity:
            warnings.append(f"Projected evacuees ({shelter_demand}) exceed total shelter capacity ({shelter.capacity})!")

        return ScenarioPreviewResponse(
            scenario_name=scenario.name,
            disaster_type=disaster.type,
            severity=disaster.severity.value,
            epicenter={"latitude": disaster.latitude, "longitude": disaster.longitude},
            radius_km=disaster.radius_km,
            affected_population=affected_pop,
            estimated_casualties_low=cas_low,
            estimated_casualties_high=cas_high,
            estimated_evacuees=evacuees,
            hospital_demand_beds=hospital_demand,
            shelter_demand_beds=shelter_demand,
            resource_coverage_ratio=resource_coverage,
            baseline_risk_score=risk_score,
            risk_level=risk_level,
            risk_factors=risk_factors,
            warnings=warnings,
        )
