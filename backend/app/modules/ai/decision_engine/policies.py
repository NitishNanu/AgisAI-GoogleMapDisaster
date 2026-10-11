"""
AegisAI Decision Engine — Policy Implementations.

Implements standard AI Decision Strategy Policies:
- NearestResourcePolicy (BASELINE benchmark)
- WeightedDispatchPolicy (HEURISTIC multi-criteria)
- OptimizationPolicy (GLOBAL OPTIMIZATION via bipartite matching)
- MLAssistedPolicy (ML PREDICTION-WEIGHTED optimization)
"""

from typing import Any, Protocol

import structlog

from app.modules.ai.decision_engine.candidates import CandidateGenerator
from app.modules.ai.decision_engine.explanation import ExplanationBuilder
from app.modules.ai.decision_engine.optimizer import GlobalAssignmentOptimizer
from app.modules.ai.decision_engine.scoring import ScoringEngine
from app.modules.ai.enums import DecisionStatus, DecisionType, PolicyType
from app.modules.ai.schemas import (
    DecisionCandidateDTO,
    DecisionState,
    DispatchScoringPolicyConfig,
    IncidentStateDTO,
)

logger = structlog.get_logger("aegis_ai.decision_engine.policies")


class DecisionPolicy(Protocol):
    """Protocol for pluggable decision strategies."""

    policy_type: PolicyType
    version: str

    async def generate_decisions(
        self,
        state: DecisionState,
        custom_weights: DispatchScoringPolicyConfig | None = None,
    ) -> list[dict[str, Any]]:
        """Generates list of structured decision dictionaries for the state."""
        ...


class NearestResourcePolicy:
    """BASELINE Policy: Selects the nearest available resource independently per incident."""

    policy_type = PolicyType.BASELINE
    version = "1.0.0"

    def __init__(self, candidate_generator: CandidateGenerator | None = None) -> None:
        self.candidate_generator = candidate_generator or CandidateGenerator()

    async def generate_decisions(
        self,
        state: DecisionState,
        custom_weights: DispatchScoringPolicyConfig | None = None,
    ) -> list[dict[str, Any]]:
        decisions: list[dict[str, Any]] = []
        assigned_resource_ids: set[int] = set()

        for inc in state.incidents:
            candidates = await self.candidate_generator.generate_candidates_for_incident(
                incident=inc,
                resources=state.resources,
                hospitals=state.hospitals,
                roads=state.roads,
                weather=state.weather,
            )

            valid_candidates = [
                c
                for c in candidates
                if c.constraints_passed and c.resource_id not in assigned_resource_ids
            ]
            if not valid_candidates:
                continue

            selected = min(valid_candidates, key=lambda c: c.distance_km)
            assigned_resource_ids.add(selected.resource_id)

            explanation = ExplanationBuilder.build_structured_explanation(
                incident=inc,
                selected_candidate=selected,
                all_candidates=candidates,
                policy_name=self.policy_type.value,
                policy_version=self.version,
            )

            note = (
                f"[Baseline] Nearest unit ({selected.distance_km:.1f}km, "
                f"ETA {selected.eta_minutes:.1f}m)."
            )
            action = {
                "incident_id": inc.incident_id,
                "resource_id": selected.resource_id,
                "resource_name": selected.resource_name,
                "vehicle_type": selected.vehicle_type,
                "destination_hospital_id": selected.hospital_id,
                "destination_hospital_name": selected.hospital_name,
                "estimated_arrival_minutes": selected.eta_minutes,
                "distance_km": selected.distance_km,
                "route_geometry": selected.route_geometry,
                "recommended_notes": note,
            }

            decisions.append(
                {
                    "decision_type": DecisionType.DISPATCH_RESOURCE.value,
                    "action": action,
                    "incident_id": inc.incident_id,
                    "resource_id": selected.resource_id,
                    "destination_id": selected.hospital_id,
                    "priority": inc.severity,
                    "score": round(max(0.1, 1.0 - (selected.distance_km / 30.0)), 4),
                    "confidence": round(explanation["confidence"], 4),
                    "reasoning": explanation["reasoning"],
                    "constraints": explanation["constraints"],
                    "expected_impact": explanation["expected_impact"],
                    "alternatives": explanation["alternatives"],
                    "status": DecisionStatus.REVIEW_REQUIRED.value,
                    "policy_name": self.policy_type.value,
                    "policy_version": self.version,
                }
            )

        return decisions


class WeightedDispatchPolicy:
    """HEURISTIC Policy: Evaluates multi-criteria normalized scores independently per incident."""

    policy_type = PolicyType.HEURISTIC
    version = "1.0.0"

    def __init__(self, candidate_generator: CandidateGenerator | None = None) -> None:
        self.candidate_generator = candidate_generator or CandidateGenerator()

    async def generate_decisions(
        self,
        state: DecisionState,
        custom_weights: DispatchScoringPolicyConfig | None = None,
    ) -> list[dict[str, Any]]:
        generator = CandidateGenerator(
            scoring_engine=ScoringEngine(custom_weights) if custom_weights else None
        )
        decisions: list[dict[str, Any]] = []
        assigned_resource_ids: set[int] = set()

        for inc in state.incidents:
            candidates = await generator.generate_candidates_for_incident(
                incident=inc,
                resources=state.resources,
                hospitals=state.hospitals,
                roads=state.roads,
                weather=state.weather,
            )

            valid_candidates = [
                c
                for c in candidates
                if c.constraints_passed and c.resource_id not in assigned_resource_ids
            ]
            if not valid_candidates:
                continue

            selected = max(valid_candidates, key=lambda c: c.suitability)
            assigned_resource_ids.add(selected.resource_id)

            explanation = ExplanationBuilder.build_structured_explanation(
                incident=inc,
                selected_candidate=selected,
                all_candidates=candidates,
                policy_name=self.policy_type.value,
                policy_version=self.version,
            )

            note = f"[Heuristic] Score: {selected.suitability:.2f}."
            action = {
                "incident_id": inc.incident_id,
                "resource_id": selected.resource_id,
                "resource_name": selected.resource_name,
                "vehicle_type": selected.vehicle_type,
                "destination_hospital_id": selected.hospital_id,
                "destination_hospital_name": selected.hospital_name,
                "estimated_arrival_minutes": selected.eta_minutes,
                "distance_km": selected.distance_km,
                "route_geometry": selected.route_geometry,
                "recommended_notes": note,
            }

            decisions.append(
                {
                    "decision_type": DecisionType.DISPATCH_RESOURCE.value,
                    "action": action,
                    "incident_id": inc.incident_id,
                    "resource_id": selected.resource_id,
                    "destination_id": selected.hospital_id,
                    "priority": inc.severity,
                    "score": selected.suitability,
                    "confidence": round(explanation["confidence"], 4),
                    "reasoning": explanation["reasoning"],
                    "constraints": explanation["constraints"],
                    "expected_impact": explanation["expected_impact"],
                    "alternatives": explanation["alternatives"],
                    "status": DecisionStatus.REVIEW_REQUIRED.value,
                    "policy_name": self.policy_type.value,
                    "policy_version": self.version,
                }
            )

        return decisions


class OptimizationPolicy:
    """OPTIMIZED Policy: Solves global multi-incident assignment via scipy LSA matching."""

    policy_type = PolicyType.OPTIMIZED
    version = "2.0.0-scipy"

    def __init__(self, candidate_generator: CandidateGenerator | None = None) -> None:
        self.candidate_generator = candidate_generator or CandidateGenerator()

    async def generate_decisions(
        self,
        state: DecisionState,
        custom_weights: DispatchScoringPolicyConfig | None = None,
    ) -> list[dict[str, Any]]:
        generator = CandidateGenerator(
            scoring_engine=ScoringEngine(custom_weights) if custom_weights else None
        )

        candidates_by_incident: dict[int, list[DecisionCandidateDTO]] = {}
        for inc in state.incidents:
            cands = await generator.generate_candidates_for_incident(
                incident=inc,
                resources=state.resources,
                hospitals=state.hospitals,
                roads=state.roads,
                weather=state.weather,
            )
            candidates_by_incident[inc.incident_id] = cands

        # Returns OptimizationResult — unpack .assignments
        opt_result = GlobalAssignmentOptimizer.solve_optimal_assignment(
            incidents=state.incidents,
            candidates_by_incident=candidates_by_incident,
        )
        optimal_matches = opt_result.assignments
        policy_used = opt_result.policy_used
        fallback_reason = opt_result.fallback_reason

        decisions: list[dict[str, Any]] = []
        for inc in state.incidents:
            selected = optimal_matches.get(inc.incident_id)
            if not selected:
                continue

            all_cands = candidates_by_incident.get(inc.incident_id, [])
            explanation = ExplanationBuilder.build_structured_explanation(
                incident=inc,
                selected_candidate=selected,
                all_candidates=all_cands,
                policy_name=self.policy_type.value,
                policy_version=self.version,
            )

            p_sev = inc.severity
            note = (
                f"[Optimized/{policy_used}] Matched "
                f"(Score: {selected.suitability:.2f}, Priority: {p_sev})."
                + (f" Fallback: {fallback_reason}" if fallback_reason else "")
            )
            action = {
                "incident_id": inc.incident_id,
                "resource_id": selected.resource_id,
                "resource_name": selected.resource_name,
                "vehicle_type": selected.vehicle_type,
                "destination_hospital_id": selected.hospital_id,
                "destination_hospital_name": selected.hospital_name,
                "estimated_arrival_minutes": selected.eta_minutes,
                "distance_km": selected.distance_km,
                "route_geometry": selected.route_geometry,
                "recommended_notes": note,
            }

            decisions.append(
                {
                    "decision_type": DecisionType.DISPATCH_RESOURCE.value,
                    "action": action,
                    "incident_id": inc.incident_id,
                    "resource_id": selected.resource_id,
                    "destination_id": selected.hospital_id,
                    "priority": inc.severity,
                    "score": selected.suitability,
                    "confidence": round(explanation["confidence"], 4),
                    "reasoning": explanation["reasoning"],
                    "constraints": explanation["constraints"],
                    "expected_impact": explanation["expected_impact"],
                    "alternatives": explanation["alternatives"],
                    "status": DecisionStatus.REVIEW_REQUIRED.value,
                    "policy_name": self.policy_type.value,
                    "policy_version": self.version,
                    "optimizer_policy_used": policy_used,
                    "optimizer_fallback_reason": fallback_reason,
                }
            )

        return decisions


class MLAssistedPolicy:
    """ML_ASSISTED Policy: Incorporates real XGBoost severity inference into multi-resource matching."""

    policy_type = PolicyType.ML_ASSISTED
    version = "2.0.0-xgb"

    def __init__(self, candidate_generator: CandidateGenerator | None = None) -> None:
        self.candidate_generator = candidate_generator or CandidateGenerator()

    async def generate_decisions(
        self,
        state: DecisionState,
        custom_weights: DispatchScoringPolicyConfig | None = None,
    ) -> list[dict[str, Any]]:
        from app.modules.ml_intelligence.severity_model import DisasterSeverityModel

        model = DisasterSeverityModel.get_instance()
        wind = getattr(state.weather, "wind_speed_kmh", 15.0) if state.weather else 15.0
        rain = getattr(state.weather, "rainfall_mm", 0.0) if state.weather else 0.0

        augmented_incidents: list[IncidentStateDTO] = []
        for inc in state.incidents:
            pred = model.predict_severity({
                "estimated_casualties": inc.estimated_casualties,
                "critical_patients": inc.critical_patients,
                "affected_radius_meters": inc.affected_radius_meters,
                "disaster_type": inc.disaster_type,
                "priority": inc.priority,
                "wind_speed_kmh": wind,
                "rainfall_mm": rain,
            })
            ml_mult = pred["severity_multiplier"]
            ml_sev = pred["predicted_severity"]

            aug = IncidentStateDTO(
                incident_id=inc.incident_id,
                title=inc.title,
                disaster_type=inc.disaster_type,
                severity=ml_sev if pred["confidence"] >= 0.5 else inc.severity,
                priority=inc.priority,
                latitude=inc.latitude,
                longitude=inc.longitude,
                affected_radius_meters=inc.affected_radius_meters * ml_mult,
                estimated_affected_people=inc.estimated_affected_people,
                estimated_casualties=inc.estimated_casualties,
                critical_patients=inc.critical_patients,
                status=inc.status,
                created_at=inc.created_at,
            )
            augmented_incidents.append(aug)

        augmented_state = DecisionState(
            incidents=augmented_incidents,
            resources=state.resources,
            hospitals=state.hospitals,
            shelters=state.shelters,
            roads=state.roads,
            weather=state.weather,
            traffic=state.traffic,
            simulation_id=state.simulation_id,
            execution_mode=state.execution_mode,
            timestamp=state.timestamp,
        )

        opt_policy = OptimizationPolicy(candidate_generator=self.candidate_generator)
        decisions = await opt_policy.generate_decisions(augmented_state, custom_weights)
        for d in decisions:
            d["policy_name"] = self.policy_type.value
            d["policy_version"] = self.version
            d["confidence"] = round(min(0.99, d["confidence"] * 1.05), 4)
            d["reasoning"].insert(0, "XGBoost ML severity scoring & spread model applied.")

        return decisions
