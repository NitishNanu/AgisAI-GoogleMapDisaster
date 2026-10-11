"""
AegisAI AI Agents Module — Scenario Architect Agent.

Role: Disaster Blueprint Designer & Simulation Director Agent.
Capabilities:
- Natural Language to Valid Scenario Blueprint Generation
- Scenario Balance, Casualty Surge & Stress-Testing Simulator
- Dynamic Cascading Crisis Timeline Injects Generator
"""

import math
from typing import Any

import structlog

from app.modules.ai.agents.base import BaseAgent
from app.modules.ai.agents.schemas import (
    ScenarioInjectEvent,
    ScenarioPromptGenerateRequest,
    ScenarioStressTestResult,
)

logger = structlog.get_logger("aegis_ai.agents.scenario")


class ScenarioArchitectAgent(BaseAgent):
    """
    Dedicated AI Agent for Emergency Scenario Design, Blueprint Synthesis,
    Stress-Test Simulations, and Dynamic Injected Event Generation.
    """

    def __init__(self) -> None:
        super().__init__(
            agent_name="ScenarioArchitectAgent",
            domain_role="Scenario Architect & Disaster Blueprint Director",
        )

    async def generate_blueprint_from_prompt(
        self,
        request: ScenarioPromptGenerateRequest,
    ) -> dict[str, Any]:
        """
        Parses natural language prompt into a complete, validated ScenarioCreate configuration.
        """
        prompt_lower = request.prompt.lower()

        # Deterministic keyword detection baseline
        dtype = "EARTHQUAKE"
        sev = "HIGH"
        if "fire" in prompt_lower or "chemical" in prompt_lower or "explosion" in prompt_lower or "gas" in prompt_lower:
            dtype = "FIRE" if "fire" in prompt_lower else ("GAS_LEAK" if "gas" in prompt_lower else "CHEMICAL_SPILL")
        elif "flood" in prompt_lower or "cyclone" in prompt_lower or "storm" in prompt_lower or "hurricane" in prompt_lower:
            dtype = "FLOOD" if "flood" in prompt_lower else "STORM"
        elif "building" in prompt_lower or "collapse" in prompt_lower or "structural" in prompt_lower:
            dtype = "BUILDING_COLLAPSE"

        if "catastrophic" in prompt_lower or "massive" in prompt_lower or "mega" in prompt_lower or request.difficulty_level == "CATASTROPHIC":
            sev = "CRITICAL"
        elif "severe" in prompt_lower or request.difficulty_level == "SEVERE":
            sev = "SEVERE"
        elif "minor" in prompt_lower or request.difficulty_level == "LOW":
            sev = "LOW"

        # Coordinates around default center
        lat = 30.7399
        lon = 76.7830

        blueprint = {
            "name": f"AI Scenario: {request.prompt[:40].strip()}...",
            "description": f"AI-Synthesized crisis simulation based on prompt: '{request.prompt}'. Configured for difficulty: {request.difficulty_level}.",
            "disaster": {
                "type": dtype,
                "severity": sev,
                "latitude": lat,
                "longitude": lon,
                "radius_km": 6.5 if sev in ("CRITICAL", "SEVERE") else 4.0,
                "magnitude": 7.2 if dtype == "EARTHQUAKE" else None,
                "depth_km": 10.0 if dtype == "EARTHQUAKE" else None,
            },
            "environment": {
                "weather_preset": "STORM" if dtype in ("FLOOD", "STORM") else "CLEAR",
                "temperature_celsius": 32.0 if dtype == "FIRE" else 24.0,
                "humidity_percent": 85 if dtype in ("FLOOD", "STORM") else 45,
                "wind_speed_kmh": 35.0 if dtype in ("FIRE", "STORM") else 12.0,
                "visibility_km": 4.0 if dtype in ("FIRE", "STORM", "GAS_LEAK") else 10.0,
            },
            "population": {
                "count": 75000 if sev in ("CRITICAL", "SEVERE") else 45000,
                "density": "DENSE" if sev == "CRITICAL" else "HIGH",
                "vulnerable_percentage": 18.5,
            },
            "resources": {
                "ambulances": 14,
                "fire_trucks": 10 if dtype in ("FIRE", "EXPLOSION", "GAS_LEAK") else 6,
                "police_units": 16,
                "rescue_teams": 12,
                "drones": 6,
                "helicopters": 3 if sev in ("CRITICAL", "SEVERE") else 1,
            },
            "hospitals": {
                "total_beds": 1600,
                "icu_beds": 210,
                "emergency_capacity_level": "CRITICAL" if sev == "CRITICAL" else "HIGH",
            },
            "shelters": {
                "capacity": 9500,
                "initial_occupancy": 500,
            },
            "infrastructure": {
                "road_damage_percentage": 25.0 if dtype in ("EARTHQUAKE", "FLOOD") else 10.0,
                "road_closure_percentage": 15.0 if dtype in ("EARTHQUAKE", "FLOOD") else 8.0,
                "bridge_damage_percentage": 12.0 if dtype in ("EARTHQUAKE", "FLOOD") else 2.0,
                "power_outage_percentage": 35.0 if sev in ("CRITICAL", "SEVERE") else 15.0,
            },
            "simulation": {
                "duration_minutes": 60,
                "speed": 2.0,
                "random_seed": 42,
            },
        }

        # Optional LLM refinement
        system_prompt = (
            "You are AegisAI's Scenario Architect Agent. Given the user's disaster prompt, refine the "
            "scenario name and description to be highly realistic, tactical, and cinematic."
        )
        user_prompt = f"User Prompt: {request.prompt}\nDifficulty: {request.difficulty_level}\nReturn JSON with 'name' and 'description'."
        llm_res = await self.call_llm(system_prompt, user_prompt)
        if llm_res and "name" in llm_res and "description" in llm_res:
            blueprint["name"] = llm_res["name"]
            blueprint["description"] = llm_res["description"]

        return blueprint

    def generate_timeline_injects(
        self,
        disaster_type: str,
        severity: str,
    ) -> list[ScenarioInjectEvent]:
        """Generates synchronized multi-stage crisis inject events."""
        injects = [
            ScenarioInjectEvent(
                minute_mark=10,
                event_type="SECONDARY_HAZARD",
                title="Secondary Utility Rupture",
                description="High pressure gas line ignition reported in adjacent commercial strip.",
                impact_description="Expands hazard perimeter by +20% and creates local road closure.",
                affected_radius_multiplier=1.2,
                additional_casualties=6,
            ),
            ScenarioInjectEvent(
                minute_mark=22,
                event_type="INFRASTRUCTURE_FAILURE",
                title="Substation Power Grid Trip",
                description="Regional distribution transformer 3B trips due to radiant thermal surge.",
                impact_description="Disrupts traffic signaling across 4 intersections and forces backup generator mode in Sector 2 clinic.",
                affected_radius_multiplier=1.0,
                additional_casualties=2,
            ),
            ScenarioInjectEvent(
                minute_mark=35,
                event_type="CASUALTY_SURGE",
                title="Multi-Story Structural Collapse",
                description="Secondary tremor precipitates collapse of partially damaged wing in residential tower.",
                impact_description="Generates surge of 15 trapped victims requiring immediate heavy extrication gear.",
                affected_radius_multiplier=1.1,
                additional_casualties=15,
            ),
            ScenarioInjectEvent(
                minute_mark=50,
                event_type="WEATHER_SHIFT",
                title="Surface Wind Vector Rotation",
                description="Wind shifts 60 degrees clockwise with gust velocity increasing to 45 km/h.",
                impact_description="Directs smoke and hazard plume towards secondary designated evacuation shelter.",
                affected_radius_multiplier=1.3,
                additional_casualties=4,
            ),
        ]
        return injects

    async def stress_test_scenario(
        self,
        scenario_config: dict[str, Any],
    ) -> ScenarioStressTestResult:
        """
        Runs a simulation curve stress test on a scenario blueprint, evaluating
        casualty surge, hospital ICU saturation, and fleet exhaustion.
        """
        disaster = scenario_config.get("disaster", {})
        resources = scenario_config.get("resources", {})
        hospitals = scenario_config.get("hospitals", {})

        dtype = disaster.get("type", "EARTHQUAKE")
        sev = disaster.get("severity", "HIGH")
        _total_pop = scenario_config.get("population", {}).get("count", 50000)

        ambulances = resources.get("ambulances", 10)
        icu_beds = hospitals.get("icu_beds", 150)

        # Baseline peak casualty multiplier based on severity
        sev_mult = 1.0
        if sev == "CRITICAL":
            sev_mult = 2.4
        elif sev == "SEVERE":
            sev_mult = 1.8
        elif sev == "HIGH":
            sev_mult = 1.3
        else:
            sev_mult = 0.8

        duration = 60
        curve: list[dict[str, Any]] = []
        projected_total_casualties = 0
        peak_minute = 25
        max_active_casualties = 0
        icu_saturation_min = None
        fleet_exhaustion_min = None

        injects = self.generate_timeline_injects(dtype, sev)

        for minute in range(0, duration + 1, 5):
            # Surge curve modeling (gamma / lognormal-like)
            t_factor = math.exp(-((minute - peak_minute) ** 2) / (2 * (15 ** 2)))
            active_casualties = int(t_factor * 85.0 * sev_mult)

            # Add inject casualties
            for inj in injects:
                if inj.minute_mark <= minute < inj.minute_mark + 15:
                    active_casualties += inj.additional_casualties

            critical_cases = int(active_casualties * 0.35)
            evacuating = int(active_casualties * 2.5)

            if active_casualties > max_active_casualties:
                max_active_casualties = active_casualties

            # Check ICU saturation
            if critical_cases > icu_beds and icu_saturation_min is None and minute > 0:
                icu_saturation_min = minute

            # Check Fleet exhaustion (assuming 2 patients per ambulance)
            ambulance_capacity = ambulances * 2
            if active_casualties > ambulance_capacity and fleet_exhaustion_min is None and minute > 0:
                fleet_exhaustion_min = minute

            curve.append({
                "minute": minute,
                "active_casualties": active_casualties,
                "critical_cases": critical_cases,
                "evacuating_citizens": evacuating,
                "icu_utilization_pct": min(100.0, round((critical_cases / max(1, icu_beds)) * 100.0, 1)),
                "fleet_utilization_pct": min(100.0, round((active_casualties / max(1, ambulance_capacity)) * 100.0, 1)),
            })

        projected_total_casualties = int(max_active_casualties * 1.8)

        # Preparedness Score calculation (0-100)
        # Penalties for early ICU saturation and fleet exhaustion
        preparedness = 88.0
        if icu_saturation_min is not None:
            preparedness -= (60 - icu_saturation_min) * 0.4
        if fleet_exhaustion_min is not None:
            preparedness -= (60 - fleet_exhaustion_min) * 0.35
        preparedness = max(20.0, min(98.0, round(preparedness, 1)))

        difficulty_rating = "EXTREME" if preparedness < 50 else ("HIGH" if preparedness < 75 else "BALANCED")
        bottleneck = "Fleet Deficit (Ambulance Transport Shortage)" if fleet_exhaustion_min and (not icu_saturation_min or fleet_exhaustion_min <= icu_saturation_min) else (
            "ICU Bed Capacity Overload" if icu_saturation_min else "Road Ingress Damage"
        )

        recs = [
            f"Pre-stage {max(4, int(ambulances * 0.3))} additional transport units along primary arterial road.",
            f"Establish regional mutual-aid agreement to divert critical patients to tier-2 trauma centers before T+{icu_saturation_min or 35}m.",
            "Deploy forward emergency triage tents to relieve hospital intake bottleneck.",
        ]

        return ScenarioStressTestResult(
            scenario_name=scenario_config.get("name", "Disaster Blueprint"),
            difficulty_rating=difficulty_rating,
            preparedness_score=preparedness,
            peak_casualty_minute=peak_minute,
            projected_total_casualties=projected_total_casualties,
            icu_saturation_minute=icu_saturation_min,
            fleet_exhaustion_minute=fleet_exhaustion_min,
            primary_bottleneck=bottleneck,
            mitigation_recommendations=recs,
            cascading_timeline=injects,
            simulation_curve=curve,
        )
