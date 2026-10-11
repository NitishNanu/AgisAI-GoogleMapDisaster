"""
AegisAI Decision Engine — Global Multi-Incident Assignment Optimizer.

Formulates and solves global resource-to-incident allocation as a
Maximum-Weight Bipartite Matching / Linear Sum Assignment problem.

The heavy lifting is delegated to ``scipy.optimize.linear_sum_assignment``
(Jonker-Volgenant shortest-augmenting-path algorithm, O(n³) worst-case).
This replaces the previous pure-Python Kuhn-Munkres implementation that
raised ``IndexError`` on every input because internal arrays were sized ``n``
while the algorithm indexed up to ``n`` (1-based).

The engine always reports ``policy_used`` and, when it falls back to the
greedy heuristic, ``fallback_reason`` so callers can surface both in audit
logs and in the API response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

try:
    from scipy.optimize import linear_sum_assignment as _scipy_lsa  # type: ignore[import-untyped]

    _SCIPY_AVAILABLE = True
except ImportError:  # pragma: no cover – tested indirectly via the fallback path
    _SCIPY_AVAILABLE = False

from app.modules.ai.schemas import DecisionCandidateDTO, IncidentStateDTO

logger = structlog.get_logger("aegis_ai.decision_engine.optimizer")

PRIORITY_WEIGHTS: dict[str, float] = {
    "CRITICAL": 2.5,
    "HIGH": 1.7,
    "MEDIUM": 1.0,
    "LOW": 0.6,
}

# Sentinel cost for (incident, resource) pairs that cannot be matched
_INFEASIBLE_COST = 1_000.0


@dataclass
class OptimizationResult:
    """Carries the solver output together with metadata for auditability."""

    assignments: dict[int, DecisionCandidateDTO]
    policy_used: str  # "scipy_lsa" | "greedy_fallback"
    fallback_reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class GlobalAssignmentOptimizer:
    """
    Solves the global resource assignment problem using maximum-weight
    bipartite matching (Linear Sum Assignment formulation).

    Primary solver  : ``scipy.optimize.linear_sum_assignment``
    Fallback solver : greedy best-first (used only when scipy is unavailable
                      or the matrix is degenerate)

    Every call returns an ``OptimizationResult`` that includes ``policy_used``
    and ``fallback_reason`` so the calling layer can report them in its output.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def solve_optimal_assignment(
        cls,
        incidents: list[IncidentStateDTO],
        candidates_by_incident: dict[int, list[DecisionCandidateDTO]],
    ) -> OptimizationResult:
        """
        Compute globally optimal incident-to-resource matching.

        Returns
        -------
        OptimizationResult
            ``assignments``    – mapping of incident_id → best candidate
            ``policy_used``    – solver that produced the result
            ``fallback_reason``– set when the greedy fallback was triggered
        """
        if not incidents or not candidates_by_incident:
            return OptimizationResult(
                assignments={},
                policy_used="scipy_lsa",
                fallback_reason=None,
                extra={"skipped": "no_incidents_or_candidates"},
            )

        incident_list = [
            inc for inc in incidents if inc.incident_id in candidates_by_incident
        ]
        all_resource_ids: list[int] = sorted(
            {
                c.resource_id
                for cand_list in candidates_by_incident.values()
                for c in cand_list
                if c.constraints_passed
            }
        )

        if not incident_list or not all_resource_ids:
            return OptimizationResult(
                assignments={},
                policy_used="scipy_lsa",
                fallback_reason=None,
                extra={"skipped": "no_feasible_pairs"},
            )

        cost_matrix, candidate_lookup = cls._build_cost_matrix(
            incident_list, all_resource_ids, candidates_by_incident
        )

        # ── Primary: scipy LSA ──────────────────────────────────────────
        if _SCIPY_AVAILABLE:
            try:
                return cls._solve_with_scipy(
                    cost_matrix, incident_list, all_resource_ids, candidate_lookup
                )
            except Exception as exc:  # pragma: no cover
                fallback_reason = f"scipy_lsa_error:{exc}"
                logger.warning(
                    "optimizer_scipy_failed_falling_back",
                    error=str(exc),
                )
        else:
            fallback_reason = "scipy_not_installed"
            logger.warning("scipy_unavailable_using_greedy_fallback")

        # ── Fallback: greedy best-first ─────────────────────────────────
        return cls._solve_greedy(
            cost_matrix,
            incident_list,
            all_resource_ids,
            candidate_lookup,
            fallback_reason=fallback_reason,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_cost_matrix(
        incident_list: list[IncidentStateDTO],
        all_resource_ids: list[int],
        candidates_by_incident: dict[int, list[DecisionCandidateDTO]],
    ) -> tuple[np.ndarray, dict[tuple[int, int], DecisionCandidateDTO]]:
        """
        Build the rectangular cost matrix (rows=incidents, cols=resources).

        Infeasible cells are filled with ``_INFEASIBLE_COST`` so the solver
        can still find a valid assignment in a non-square matrix.
        """
        num_incidents = len(incident_list)
        num_resources = len(all_resource_ids)

        cost_matrix = np.full((num_incidents, num_resources), _INFEASIBLE_COST)
        candidate_lookup: dict[tuple[int, int], DecisionCandidateDTO] = {}

        resource_index: dict[int, int] = {
            rid: idx for idx, rid in enumerate(all_resource_ids)
        }

        for i_idx, inc in enumerate(incident_list):
            p_weight = PRIORITY_WEIGHTS.get(inc.severity.upper(), 1.0)
            for cand in candidates_by_incident.get(inc.incident_id, []):
                if cand.constraints_passed and cand.resource_id in resource_index:
                    r_idx = resource_index[cand.resource_id]
                    utility = cand.suitability * p_weight
                    cost_matrix[i_idx, r_idx] = 100.0 - utility
                    candidate_lookup[(inc.incident_id, cand.resource_id)] = cand

        return cost_matrix, candidate_lookup

    @classmethod
    def _solve_with_scipy(
        cls,
        cost_matrix: np.ndarray,
        incident_list: list[IncidentStateDTO],
        all_resource_ids: list[int],
        candidate_lookup: dict[tuple[int, int], DecisionCandidateDTO],
    ) -> OptimizationResult:
        """Run scipy.optimize.linear_sum_assignment and extract valid pairs."""
        row_ind, col_ind = _scipy_lsa(cost_matrix)

        assignments: dict[int, DecisionCandidateDTO] = {}
        for r, c in zip(row_ind, col_ind, strict=False):
            if cost_matrix[r, c] >= _INFEASIBLE_COST:
                continue  # infeasible cell – skip
            inc = incident_list[r]
            res_id = all_resource_ids[c]
            cand = candidate_lookup.get((inc.incident_id, res_id))
            if cand and cand.constraints_passed:
                assignments[inc.incident_id] = cand

        logger.info(
            "optimizer_scipy_solved",
            total_incidents=len(incident_list),
            assigned_count=len(assignments),
        )
        return OptimizationResult(
            assignments=assignments,
            policy_used="scipy_lsa",
            fallback_reason=None,
            extra={
                "total_incidents": len(incident_list),
                "total_resources": len(all_resource_ids),
                "assigned": len(assignments),
            },
        )

    @classmethod
    def _solve_greedy(
        cls,
        cost_matrix: np.ndarray,
        incident_list: list[IncidentStateDTO],
        all_resource_ids: list[int],
        candidate_lookup: dict[tuple[int, int], DecisionCandidateDTO],
        *,
        fallback_reason: str,
    ) -> OptimizationResult:
        """
        Greedy best-first fallback: assign the globally cheapest feasible
        (incident, resource) pair iteratively.
        """
        assigned_incidents: set[int] = set()
        assigned_resources: set[int] = set()
        assignments: dict[int, DecisionCandidateDTO] = {}

        # Flatten all feasible (cost, row, col) triples and sort ascending
        feasible: list[tuple[float, int, int]] = []
        rows, cols = np.where(cost_matrix < _INFEASIBLE_COST)
        for r, c in zip(rows.tolist(), cols.tolist(), strict=False):
            feasible.append((float(cost_matrix[r, c]), int(r), int(c)))
        feasible.sort()

        for _cost, r, c in feasible:
            if r in assigned_incidents or c in assigned_resources:
                continue
            inc = incident_list[r]
            res_id = all_resource_ids[c]
            cand = candidate_lookup.get((inc.incident_id, res_id))
            if cand and cand.constraints_passed:
                assignments[inc.incident_id] = cand
                assigned_incidents.add(r)
                assigned_resources.add(c)

        logger.info(
            "optimizer_greedy_solved",
            total_incidents=len(incident_list),
            assigned_count=len(assignments),
            fallback_reason=fallback_reason,
        )
        return OptimizationResult(
            assignments=assignments,
            policy_used="greedy_fallback",
            fallback_reason=fallback_reason,
            extra={
                "total_incidents": len(incident_list),
                "total_resources": len(all_resource_ids),
                "assigned": len(assignments),
            },
        )
