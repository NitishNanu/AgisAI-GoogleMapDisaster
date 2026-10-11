"""
AegisAI AI Agents Module — Incident Intelligence Agent.

Role: Incident Commander & Tactical Triage Intelligence Agent.
Capabilities:
- Real-time hazard zone envelope generation (+15m, +30m, +60m)
- Incident Action Plan (IAP) generator with tactical objectives
- Secondary disaster & cascading threat risk analyzer
- Resource requirement sizing & safe staging area placement
"""

import math
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.modules.ai.agents.base import BaseAgent
from app.modules.ai.agents.schemas import (
    HazardEnvelopeResponse,
    HazardZoneEnvelope,
    IncidentActionPlan,
    SecondaryCascadeRisk,
    TacticalObjective,
)
from app.modules.incident.models import Incident
from app.modules.simulation.schemas import WeatherCondition

logger = structlog.get_logger("aegis_ai.agents.incident")


class IncidentIntelligenceAgent(BaseAgent):
    """
    Dedicated AI Agent for Emergency Incident Triage, Hazard Forecasting,
    and Incident Action Plan (IAP) Orchestration.
    """

    def __init__(self) -> None:
        super().__init__(
            agent_name="IncidentCommanderAgent",
            domain_role="Incident Command & Tactical Triage Specialist",
        )

    def calculate_hazard_envelopes(
        self,
        incident: Incident,
        weather: WeatherCondition | None = None,
    ) -> HazardEnvelopeResponse:
        """
        Calculates dynamic multi-horizon concentric / wind-skewed hazard envelopes
        for +15m, +30m, and +60m projection horizons.
        """
        base_radius = incident.affected_radius_meters or 500.0
        wind_deg = getattr(weather, "wind_direction_degrees", getattr(weather, "wind_direction_deg", 45.0)) if weather else 45.0
        wind_speed = weather.wind_speed_kmh if weather else 12.0

        # Expansion speed factor per hazard type
        type_multipliers = {
            "FIRE": 1.8,
            "GAS_LEAK": 2.2,
            "CHEMICAL_SPILL": 1.6,
            "FLOOD": 1.4,
            "EARTHQUAKE": 1.1,
            "BUILDING_COLLAPSE": 1.05,
            "STORM": 1.7,
        }
        mult = type_multipliers.get(incident.disaster_type, 1.2)

        envelopes: list[HazardZoneEnvelope] = []
        horizons = [
            (15, 1.0 + (wind_speed / 40.0) * 0.3 * mult, "RED_EVACUATE"),
            (30, 1.0 + (wind_speed / 40.0) * 0.7 * mult, "ORANGE_SHELTER"),
            (60, 1.0 + (wind_speed / 40.0) * 1.3 * mult, "YELLOW_ADVISORY"),
        ]

        center_lat = incident.latitude
        center_lon = incident.longitude

        for mins, factor, threat in horizons:
            radius = base_radius * factor
            area_sq_km = math.pi * (radius / 1000.0) ** 2

            # Compute wind-offset polygon circle (12 points)
            poly_points = []
            wind_rad = math.radians(wind_deg)
            offset_dist_m = (wind_speed / 3.6) * (mins * 60) * 0.08  # slight wind drift

            drift_lat = center_lat + (offset_dist_m * math.cos(wind_rad)) / 111320.0
            drift_lon = center_lon + (offset_dist_m * math.sin(wind_rad)) / (
                111320.0 * math.cos(math.radians(center_lat))
            )

            for step in range(12):
                angle = step * (360.0 / 12.0)
                angle_rad = math.radians(angle)
                lat_p = drift_lat + (radius * math.cos(angle_rad)) / 111320.0
                lon_p = drift_lon + (radius * math.sin(angle_rad)) / (
                    111320.0 * math.cos(math.radians(drift_lat))
                )
                poly_points.append([round(lat_p, 6), round(lon_p, 6)])

            envelopes.append(
                HazardZoneEnvelope(
                    horizon_minutes=mins,
                    radius_meters=round(radius, 1),
                    area_sq_km=round(area_sq_km, 3),
                    threat_level=threat,
                    wind_adjusted_bearing_deg=round(wind_deg, 1),
                    polygon_coordinates=poly_points,
                )
            )

        pop_density = 400.0  # citizens per sq km baseline
        endangered_pop = int(envelopes[-1].area_sq_km * pop_density)

        return HazardEnvelopeResponse(
            incident_id=incident.id,
            center_latitude=center_lat,
            center_longitude=center_lon,
            current_radius_meters=base_radius,
            wind_direction_deg=wind_deg,
            wind_speed_kmh=wind_speed,
            envelopes=envelopes,
            evacuation_zone_area_sq_km=envelopes[0].area_sq_km,
            estimated_endangered_population=max(
                endangered_pop, incident.estimated_affected_people or 0
            ),
        )

    def _determine_cascade_risks(self, disaster_type: str, severity: str) -> list[SecondaryCascadeRisk]:
        """Algorithmic secondary risk identification."""
        risks = []
        if disaster_type in ("EARTHQUAKE", "BUILDING_COLLAPSE"):
            risks.append(
                SecondaryCascadeRisk(
                    hazard_type="GAS_LEAK_AND_FIRE",
                    probability_pct=78.0 if severity in ("HIGH", "CRITICAL") else 45.0,
                    trigger_condition="Subsurface gas utility rupture caused by seismic shear stress.",
                    mitigation_action="Isolate sector gas mains and dispatch Hazmat unit with combustible gas sniffers.",
                )
            )
            risks.append(
                SecondaryCascadeRisk(
                    hazard_type="SECONDARY_AFTERSHOCK_COLLAPSE",
                    probability_pct=65.0,
                    trigger_condition="Compromised structural columns vulnerable to secondary tremors.",
                    mitigation_action="Establish 1.5x building height collapse exclusion zone.",
                )
            )
        elif disaster_type in ("FIRE", "EXPLOSION", "CHEMICAL_SPILL"):
            risks.append(
                SecondaryCascadeRisk(
                    hazard_type="TOXIC_PLUME_DRIFT",
                    probability_pct=85.0,
                    trigger_condition="Combustion particulate carried by surface winds toward residential quarters.",
                    mitigation_action="Issue Level-2 Shelter-in-Place and distribute N95 respirators downwind.",
                )
            )
            risks.append(
                SecondaryCascadeRisk(
                    hazard_type="ELECTRICAL_GRID_FLASH",
                    probability_pct=52.0,
                    trigger_condition="Transformer station proximity to radiant heat source.",
                    mitigation_action="Coordinate grid operator emergency power cut on feeder line 4B.",
                )
            )
        elif disaster_type in ("FLOOD", "STORM"):
            risks.append(
                SecondaryCascadeRisk(
                    hazard_type="ROAD_WASHOUT_AND_ISOLATION",
                    probability_pct=72.0,
                    trigger_condition="Storm drain saturation exceeding 120mm/hr capacity.",
                    mitigation_action="Deploy inflatable flood barriers and reroute emergency convoys to elevated arterial roads.",
                )
            )
        else:
            risks.append(
                SecondaryCascadeRisk(
                    hazard_type="COMMUNICATION_DISRUPTION",
                    probability_pct=40.0,
                    trigger_condition="Local cellular repeater load congestion during panic surge.",
                    mitigation_action="Deploy mobile tactical radio relay mast at staging area.",
                )
            )
        return risks

    def _determine_resource_matrix(self, disaster_type: str, severity: str, casualties: int) -> dict[str, int]:
        """Calculates exact required response fleet sizing."""
        sev_factor = 3 if severity in ("CRITICAL", "SEVERE") else (2 if severity == "HIGH" else 1)
        ambulance_count = max(2, math.ceil(casualties / 4)) * sev_factor

        matrix = {
            "AMBULANCE": min(12, ambulance_count),
            "FIRE_ENGINE": 2 * sev_factor if disaster_type in ("FIRE", "EXPLOSION", "GAS_LEAK") else 1,
            "RESCUE_TEAM": 2 * sev_factor if disaster_type in ("EARTHQUAKE", "BUILDING_COLLAPSE", "FLOOD") else 1,
            "POLICE_PATROL": 2 * sev_factor,
            "DRONE": 1 * sev_factor,
            "HAZMAT": 2 if disaster_type in ("CHEMICAL_SPILL", "GAS_LEAK", "INDUSTRIAL_ACCIDENT") else 0,
        }
        return {k: v for k, v in matrix.items() if v > 0}

    async def generate_incident_action_plan(
        self,
        db: Session,
        incident_id: int,
        weather: WeatherCondition | None = None,
    ) -> IncidentActionPlan:
        """
        Synthesizes a full Incident Action Plan (IAP) combining deterministic
        geospatial/hazard modeling with tactical LLM commander reasoning.
        """
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            raise ValueError(f"Incident #{incident_id} not found in database.")

        reasoning_steps = [
            f"Ingested telemetry for Incident #{incident.id}: '{incident.title}' [{incident.disaster_type}, {incident.severity}]",
            f"Geospatial Anchor: ({incident.latitude:.5f}, {incident.longitude:.5f}), Base Radius: {incident.affected_radius_meters or 500}m",
            "Executed multi-horizon hazard spread calculation (+15m, +30m, +60m)",
            "Evaluated secondary cascade hazards and structural vulnerability matrix",
            "Determined upwind Staging Area coordinates and safe operational perimeter",
        ]

        # 1. Envelopes
        env_res = self.calculate_hazard_envelopes(incident, weather)
        envelopes = env_res.envelopes

        # 2. Staging Area (Upwind 800m offset from center)
        wind_deg = getattr(weather, "wind_direction_degrees", getattr(weather, "wind_direction_deg", 45.0)) if weather else 45.0
        upwind_rad = math.radians((wind_deg + 180.0) % 360.0)
        staging_lat = incident.latitude + (800.0 * math.cos(upwind_rad)) / 111320.0
        staging_lon = incident.longitude + (800.0 * math.sin(upwind_rad)) / (
            111320.0 * math.cos(math.radians(incident.latitude))
        )
        staging_area = {
            "name": f"Forward Staging Area Alpha ({incident.disaster_type})",
            "latitude": round(staging_lat, 6),
            "longitude": round(staging_lon, 6),
            "safe_distance_meters": 800.0,
            "access_corridor": "Primary upwind arterial highway",
        }

        # 3. Cascade risks & Resources
        cascade_risks = self._determine_cascade_risks(incident.disaster_type, incident.severity)
        required_resources = self._determine_resource_matrix(
            incident.disaster_type,
            incident.severity,
            incident.estimated_casualties or 4,
        )

        # 4. Tactical Objectives
        tactical_objectives = [
            TacticalObjective(
                id="OBJ-01",
                phase="IMMEDIATE",
                objective="Establish outer perimeter cordon at 500m radius and clear primary ingress/egress route.",
                assigned_unit_type="POLICE_PATROL",
                target_time_minutes=10,
                priority="CRITICAL",
            ),
            TacticalObjective(
                id="OBJ-02",
                phase="IMMEDIATE",
                objective="Conduct search & extrication of critical trapped casualties in immediate impact zone.",
                assigned_unit_type="RESCUE_TEAM",
                target_time_minutes=20,
                priority="CRITICAL",
            ),
            TacticalObjective(
                id="OBJ-03",
                phase="STABILIZATION",
                objective="Establish forward triage post at Staging Area Alpha and execute rapid trauma stabilization.",
                assigned_unit_type="AMBULANCE",
                target_time_minutes=30,
                priority="HIGH",
            ),
            TacticalObjective(
                id="OBJ-04",
                phase="CONTAINMENT",
                objective="Deploy thermal drone reconnaissance to monitor hazard perimeter progression.",
                assigned_unit_type="DRONE",
                target_time_minutes=45,
                priority="HIGH",
            ),
        ]

        # Containment percentage estimation
        containment_pct = 25.0 if incident.status == "ACTIVE" else (75.0 if incident.status == "CONTAINED" else 10.0)

        # 5. LLM Synthesis (if available)
        system_prompt = (
            "You are AegisAI's Incident Commander Agent. Given the incident facts and tactical analysis, "
            "generate a concise military-grade executive commander summary."
        )
        user_prompt = (
            f"Incident: {incident.title} ({incident.disaster_type}, Severity: {incident.severity})\n"
            f"Location: ({incident.latitude}, {incident.longitude})\n"
            f"Casualties: {incident.estimated_casualties}, Critical: {incident.critical_patients}\n"
            f"Staging Area: {staging_area['name']}\n"
            f"Resources Required: {required_resources}\n"
            f"Cascade Risks: {[r.hazard_type for r in cascade_risks]}\n"
            "Return JSON with key: 'commander_summary'."
        )

        llm_res = await self.call_llm(system_prompt, user_prompt)
        commander_summary = ""
        if llm_res and "commander_summary" in llm_res:
            commander_summary = llm_res["commander_summary"]
            reasoning_steps.append("Enhanced commander briefing with Ollama LLM reasoning.")
        else:
            commander_summary = (
                f"INCIDENT COMMAND DIRECTIVE: Immediate mobilization initiated for {incident.title}. "
                f"Establish hot-zone perimeter at {envelopes[0].radius_meters}m. Direct all responding units "
                f"to report to {staging_area['name']}. Prioritize rapid extrication and stabilization of "
                f"{incident.critical_patients or incident.estimated_casualties or 2} critical patients."
            )
            reasoning_steps.append("Generated deterministic military-grade commander directive.")

        return IncidentActionPlan(
            incident_id=incident.id,
            incident_title=incident.title,
            severity=incident.severity,
            disaster_type=incident.disaster_type,
            commander_summary=commander_summary,
            estimated_casualties=incident.estimated_casualties or 0,
            critical_patients=incident.critical_patients or 0,
            containment_status_pct=containment_pct,
            safety_perimeter_meters=envelopes[0].radius_meters,
            evacuation_radius_meters=envelopes[1].radius_meters,
            staging_area=staging_area,
            required_resources=required_resources,
            tactical_objectives=tactical_objectives,
            cascade_risks=cascade_risks,
            hazard_envelopes=envelopes,
            reasoning_steps=reasoning_steps,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
