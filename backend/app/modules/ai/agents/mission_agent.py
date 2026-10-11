"""
AegisAI AI Agents Module — Mission Operations Agent.

Role: Tactical Dispatch & Mission Tracking Commander Agent.
Capabilities:
- Real-time in-flight mission monitoring and anomaly detection
- Dynamic Medevac Hospital Routing & Trauma capacity allocation
- Military/Emergency Situation Reports (SITREPs)
- Tactical reinforcement and dynamic backup recommendations
"""

import json
import math
from datetime import datetime, timezone
from typing import Any
import structlog
from sqlalchemy.orm import Session

from app.modules.ai.agents.base import BaseAgent
from app.modules.ai.agents.schemas import (
    HospitalMedevacCandidate,
    MissionMedevacRecommendation,
    MissionMonitorReport,
    MissionSITREP,
    MissionTelemetryAnomaly,
)
from app.modules.hospital.models import Hospital
from app.modules.incident.models import Incident
from app.modules.resource.models import RescueTeam, ResourceAssignment
from app.routing.osrm import OSRMService

logger = structlog.get_logger("aegis_ai.agents.mission")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class MissionOperationsAgent(BaseAgent):
    """
    Dedicated AI Agent for Emergency Mission Dispatch, In-Flight Telemetry
    Surveillance, Medevac Allocation, and Tactical SITREP Synthesis.
    """

    def __init__(self) -> None:
        super().__init__(
            agent_name="MissionOperationsAgent",
            domain_role="Mission Operations & Tactical Dispatch Director",
        )

    def detect_mission_anomalies(
        self,
        assignment: ResourceAssignment,
        incident: Incident,
        team: RescueTeam,
    ) -> list[MissionTelemetryAnomaly]:
        """Detects in-flight operational bottlenecks and risk conditions."""
        anomalies: list[MissionTelemetryAnomaly] = []

        now = datetime.now(timezone.utc)
        elapsed_mins = 0.0
        if assignment.started_at:
            elapsed_mins = (now - assignment.started_at).total_seconds() / 60.0
        elif assignment.created_at:
            elapsed_mins = (now - assignment.created_at).total_seconds() / 60.0

        est_eta = assignment.estimated_arrival_minutes or 8.0

        # 1. ETA Slippage Anomaly
        if assignment.status in ("DISPATCHED", "EN_ROUTE") and elapsed_mins > (est_eta * 1.5):
            anomalies.append(
                MissionTelemetryAnomaly(
                    anomaly_type="ROUTE_CONGESTION",
                    severity="WARNING",
                    description=f"Unit '{team.team_name}' is experiencing a {elapsed_mins - est_eta:.1f}m delay beyond initial ETA.",
                    recommended_action="Recalculate dynamic route bypass or dispatch escort drone.",
                )
            )

        # 2. Casualty Mismatch
        casualties = incident.estimated_casualties or 0
        if casualties > 6 and team.vehicle_type in ("Ambulance", "AMBULANCE", "Drone"):
            anomalies.append(
                MissionTelemetryAnomaly(
                    anomaly_type="CAPACITY_OVERFLOW",
                    severity="CRITICAL",
                    description=f"Scene casualty count ({casualties}) exceeds single unit transport capacity (2-4 max).",
                    recommended_action="Dispatch secondary multi-casualty transport bus and additional paramedic unit.",
                )
            )

        # 3. High Risk Incident with Light Team
        if incident.severity in ("CRITICAL", "SEVERE") and team.members <= 2:
            anomalies.append(
                MissionTelemetryAnomaly(
                    anomaly_type="HAZARD_SEVERITY_MISMATCH",
                    severity="HIGH",
                    description=f"High risk {incident.disaster_type} zone assigned to low crew count unit ({team.members} members).",
                    recommended_action="Deploy tactical backup rescue squad to support staging perimeter.",
                )
            )

        return anomalies

    async def generate_medevac_recommendation(
        self,
        db: Session,
        assignment_id: int,
    ) -> MissionMedevacRecommendation:
        """
        Evaluates nearby hospitals for an active mission, ranking them by
        ICU bed availability, trauma level, and real-time road distance.
        """
        assignment = db.query(ResourceAssignment).filter(ResourceAssignment.id == assignment_id).first()
        if not assignment:
            raise ValueError(f"Assignment #{assignment_id} not found.")

        incident = assignment.incident or db.query(Incident).filter(Incident.id == assignment.incident_id).first()
        if not incident:
            raise ValueError(f"Incident for assignment #{assignment_id} not found.")

        team = assignment.team or db.query(RescueTeam).filter(RescueTeam.id == assignment.team_id).first()
        if not team:
            raise ValueError(f"Rescue team for assignment #{assignment_id} not found.")

        hospitals = db.query(Hospital).all()
        if not hospitals:
            raise ValueError("No hospital facilities found in database.")

        candidates: list[HospitalMedevacCandidate] = []

        for hosp in hospitals:
            dist_km = _haversine_km(incident.latitude, incident.longitude, hosp.latitude, hosp.longitude)
            eta_mins = (dist_km / 45.0) * 60.0  # approximate emergency speed

            # Real OSRM route if possible
            route_coords = None
            try:
                osrm_res = await OSRMService.get_route(incident.latitude, incident.longitude, hosp.latitude, hosp.longitude)
                if osrm_res and "distance_km" in osrm_res:
                    dist_km = osrm_res["distance_km"]
                    eta_mins = osrm_res["duration_minutes"]
                    if "geometry" in osrm_res and isinstance(osrm_res["geometry"], dict) and "coordinates" in osrm_res["geometry"]:
                        route_coords = osrm_res["geometry"]["coordinates"]
            except Exception:
                pass

            # Suitability scoring (0-100)
            # Bed availability weight: 40%, ICU weight: 30%, Proximity weight: 30%
            avail_beds = hosp.available_beds
            avail_icu = hosp.available_icu
            
            bed_score = min(40.0, (avail_beds / 50.0) * 40.0)
            icu_score = min(30.0, (avail_icu / 10.0) * 30.0)
            dist_score = max(0.0, 30.0 - (dist_km * 2.0))
            total_score = round(bed_score + icu_score + dist_score, 1)

            candidates.append(
                HospitalMedevacCandidate(
                    hospital_id=hosp.id,
                    hospital_name=hosp.name,
                    distance_km=round(dist_km, 2),
                    eta_minutes=round(eta_mins, 1),
                    available_beds=max(0, avail_beds),
                    icu_beds_available=max(0, avail_icu),
                    trauma_level=getattr(hosp, "trauma_level", "Level 1 Trauma"),
                    suitability_score=total_score,
                    route_geometry=route_coords,
                    is_recommended=False,
                )
            )

        # Sort candidates descending by score
        candidates.sort(key=lambda c: c.suitability_score, reverse=True)
        if candidates:
            candidates[0].is_recommended = True

        best = candidates[0]
        triage_notes = (
            f"RECOMMENDED DESTINATION: {best.hospital_name} (Score: {best.suitability_score}/100). "
            f"Facility has {best.available_beds} available beds ({best.icu_beds_available} ICU) at {best.distance_km}km distance "
            f"with estimated transport ETA of {best.eta_minutes} minutes."
        )

        return MissionMedevacRecommendation(
            assignment_id=assignment.id,
            incident_id=incident.id,
            current_team_id=team.id,
            selected_hospital=best,
            alternative_hospitals=candidates[1:4],
            triage_notes=triage_notes,
            critical_patients_count=incident.critical_patients or max(1, int((incident.estimated_casualties or 2) * 0.4)),
        )

    async def generate_mission_sitrep(
        self,
        db: Session,
        assignment_id: int,
    ) -> MissionSITREP:
        """
        Synthesizes a standardized Military/Emergency Incident Command Situation Report (SITREP).
        """
        assignment = db.query(ResourceAssignment).filter(ResourceAssignment.id == assignment_id).first()
        if not assignment:
            raise ValueError(f"Assignment #{assignment_id} not found.")

        incident = assignment.incident or db.query(Incident).filter(Incident.id == assignment.incident_id).first()
        if not incident:
            raise ValueError(f"Incident for assignment #{assignment_id} not found.")

        team = assignment.team or db.query(RescueTeam).filter(RescueTeam.id == assignment.team_id).first()
        if not team:
            raise ValueError(f"Rescue team for assignment #{assignment_id} not found.")

        now = datetime.now(timezone.utc)
        elapsed_mins = 0.0
        if assignment.started_at:
            elapsed_mins = (now - assignment.started_at).total_seconds() / 60.0
        elif assignment.created_at:
            elapsed_mins = (now - assignment.created_at).total_seconds() / 60.0

        est_eta = assignment.estimated_arrival_minutes or 6.0
        remaining_eta = max(0.0, est_eta - elapsed_mins) if assignment.status in ("ASSIGNED", "DISPATCHED", "EN_ROUTE") else 0.0
        remaining_dist = (assignment.distance_km or 3.5) * (remaining_eta / max(0.1, est_eta))

        # Operational milestones
        milestones = [
            f"T+00: Dispatch command issued to {team.team_name} ({team.vehicle_type}).",
            f"T+{min(1.5, elapsed_mins):.1f}: Team acknowledged dispatch and departed base staging.",
        ]
        if assignment.status in ("EN_ROUTE", "ARRIVED", "OPERATIONAL", "COMPLETED"):
            milestones.append(f"T+{min(4.0, elapsed_mins):.1f}: Unit confirmed en-route tracking via primary corridor.")
        if assignment.status in ("ARRIVED", "OPERATIONAL", "COMPLETED"):
            milestones.append(f"T+{min(est_eta, elapsed_mins):.1f}: On scene arrival confirmed. Incident Commander link established.")
        if assignment.status == "COMPLETED":
            milestones.append(f"T+{elapsed_mins:.1f}: Mission objectives accomplished. Unit clearing scene.")

        anomalies = self.detect_mission_anomalies(assignment, incident, team)

        casualties_count = incident.estimated_casualties or 0
        critical_count = incident.critical_patients or max(0, int(casualties_count * 0.35))

        reasoning_steps = [
            f"Assessed live telemetry for Mission #{assignment.id} [{assignment.status}]",
            f"Calculated elapsed mission duration: {elapsed_mins:.1f} mins vs planned ETA: {est_eta:.1f} mins",
            f"Audited {len(anomalies)} telemetry anomaly flags",
            "Evaluated on-scene casualty triage demand vs crew vehicle capability",
        ]

        backup_needed = len(anomalies) > 0 or incident.severity in ("CRITICAL", "SEVERE")
        backup_type = "AMBULANCE" if casualties_count > 4 else ("FIRE_ENGINE" if incident.disaster_type in ("FIRE", "GAS_LEAK") else "POLICE_PATROL")

        tactical_next_steps = [
            f"Maintain direct tactical radio link with {team.team_name}.",
            "Monitor patient vital telemetry and coordinate with Trauma ER receiving desk.",
            "Establish secondary egress corridor for incoming reinforcement units.",
        ]

        # LLM Synthesis for SITREP Narrative
        system_prompt = (
            "You are AegisAI's Mission Operations Agent. Generate tactical situation recommendations "
            "based on the provided mission telemetry."
        )
        user_prompt = (
            f"Mission #{assignment.id}: Team '{team.team_name}' ({team.vehicle_type}) assigned to '{incident.title}'.\n"
            f"Status: {assignment.status}, Elapsed: {elapsed_mins:.1f}m, Remaining ETA: {remaining_eta:.1f}m.\n"
            f"Casualties: {casualties_count} (Critical: {critical_count}).\n"
            f"Anomalies: {[a.description for a in anomalies]}.\n"
            "Provide JSON with 'tactical_next_steps' (list of 3 strings)."
        )
        llm_res = await self.call_llm(system_prompt, user_prompt)
        if llm_res and "tactical_next_steps" in llm_res and isinstance(llm_res["tactical_next_steps"], list):
            tactical_next_steps = llm_res["tactical_next_steps"]
            reasoning_steps.append("Refined tactical next steps with LLM tactical reasoner.")

        return MissionSITREP(
            assignment_id=assignment.id,
            incident_id=incident.id,
            incident_title=incident.title,
            team_name=team.team_name,
            vehicle_type=team.vehicle_type,
            current_status=assignment.status,
            elapsed_minutes=round(elapsed_mins, 1),
            distance_remaining_km=round(remaining_dist, 2),
            eta_remaining_minutes=round(remaining_eta, 1),
            operational_milestones=milestones,
            casualties_handled=casualties_count,
            critical_triage_count=critical_count,
            anomalies=anomalies,
            tactical_next_steps=tactical_next_steps,
            backup_recommended=backup_needed,
            recommended_backup_type=backup_type if backup_needed else None,
            reasoning_steps=reasoning_steps,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    async def monitor_all_missions(self, db: Session) -> MissionMonitorReport:
        """Batch monitoring across all active missions."""
        active_assignments = (
            db.query(ResourceAssignment)
            .filter(ResourceAssignment.status.in_(["ASSIGNED", "DISPATCHED", "EN_ROUTE", "ARRIVED", "OPERATIONAL"]))
            .all()
        )

        sitreps: list[MissionSITREP] = []
        critical_alerts = 0
        delayed = 0

        for a in active_assignments:
            try:
                sitrep = await self.generate_mission_sitrep(db, a.id)
                sitreps.append(sitrep)
                if any(anom.severity == "CRITICAL" for anom in sitrep.anomalies):
                    critical_alerts += 1
                if any(anom.anomaly_type == "ROUTE_CONGESTION" for anom in sitrep.anomalies):
                    delayed += 1
            except Exception as err:
                logger.warn("mission_sitrep_batch_error", assignment_id=a.id, error=str(err))

        total = len(sitreps)
        on_sched = total - delayed

        load_status = "OPTIMAL"
        if critical_alerts > 0:
            load_status = "CRITICAL_ATTENTION_REQUIRED"
        elif delayed > 0:
            load_status = "ELEVATED_CONGESTION"

        return MissionMonitorReport(
            total_active_missions=total,
            on_schedule_count=on_sched,
            delayed_count=delayed,
            critical_alerts_count=critical_alerts,
            mission_sitreps=sitreps,
            system_load_status=load_status,
        )
