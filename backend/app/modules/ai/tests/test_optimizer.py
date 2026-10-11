"""
Comprehensive unit tests for the GlobalAssignmentOptimizer (Task 0.1).

Covers:
 - 1×1 (trivial) matrix
 - Rectangular matrices (more resources than incidents, and vice versa)
 - All-infeasible input (no constraints_passed candidates)
 - Competing priorities (CRITICAL incident wins the best resource)
 - Brute-force comparison on small cases (exhaustive vs scipy result)
 - policy_used and fallback_reason are always present in the result
 - scipy fallback path (simulated by monkeypatching)
"""

from __future__ import annotations

import itertools

import pytest

from app.modules.ai.decision_engine.optimizer import (
    GlobalAssignmentOptimizer,
    OptimizationResult,
)
from app.modules.ai.schemas import DecisionCandidateDTO, IncidentStateDTO

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_incident(
    incident_id: int,
    severity: str = "HIGH",
    lat: float = 30.70,
    lon: float = 76.78,
) -> IncidentStateDTO:
    return IncidentStateDTO(
        incident_id=incident_id,
        disaster_type="FIRE",
        severity=severity,
        latitude=lat,
        longitude=lon,
    )


def _make_candidate(
    resource_id: int,
    incident_id: int,
    suitability: float = 0.80,
    constraints_passed: bool = True,
) -> DecisionCandidateDTO:
    return DecisionCandidateDTO(
        resource_id=resource_id,
        resource_name=f"Unit-{resource_id}",
        vehicle_type="RESCUE_VAN",
        incident_id=incident_id,
        eta_minutes=10.0,
        distance_km=5.0,
        suitability=suitability,
        constraints_passed=constraints_passed,
    )


# ---------------------------------------------------------------------------
# 1. Empty / degenerate inputs
# ---------------------------------------------------------------------------

def test_empty_incidents_returns_empty_result() -> None:
    result = GlobalAssignmentOptimizer.solve_optimal_assignment(
        incidents=[], candidates_by_incident={}
    )
    assert isinstance(result, OptimizationResult)
    assert result.assignments == {}
    assert result.policy_used in ("scipy_lsa", "greedy_fallback")


def test_empty_candidates_returns_empty_result() -> None:
    inc = _make_incident(1)
    result = GlobalAssignmentOptimizer.solve_optimal_assignment(
        incidents=[inc], candidates_by_incident={}
    )
    assert result.assignments == {}


def test_all_infeasible_candidates_returns_empty() -> None:
    """No candidate has constraints_passed=True — should produce no assignments."""
    inc = _make_incident(1, severity="CRITICAL")
    bad_cand = _make_candidate(resource_id=10, incident_id=1, constraints_passed=False)
    result = GlobalAssignmentOptimizer.solve_optimal_assignment(
        incidents=[inc],
        candidates_by_incident={1: [bad_cand]},
    )
    assert result.assignments == {}


# ---------------------------------------------------------------------------
# 2. 1×1 (single incident, single resource)
# ---------------------------------------------------------------------------

def test_one_by_one_assignment() -> None:
    inc = _make_incident(1)
    cand = _make_candidate(resource_id=10, incident_id=1, suitability=0.85)
    result = GlobalAssignmentOptimizer.solve_optimal_assignment(
        incidents=[inc],
        candidates_by_incident={1: [cand]},
    )
    assert len(result.assignments) == 1
    assert result.assignments[1].resource_id == 10
    assert result.policy_used in ("scipy_lsa", "greedy_fallback")
    # No fallback expected for a working scipy install
    assert result.fallback_reason is None or isinstance(result.fallback_reason, str)


# ---------------------------------------------------------------------------
# 3. Rectangular: more resources than incidents
# ---------------------------------------------------------------------------

def test_rectangular_more_resources_than_incidents() -> None:
    """2 incidents, 4 resources — each incident should get exactly one resource."""
    inc1 = _make_incident(1, severity="HIGH")
    inc2 = _make_incident(2, severity="MEDIUM")

    # Inc 1 can use resources 10, 11, 12
    # Inc 2 can use resources 10, 11, 13
    candidates_by_incident = {
        1: [
            _make_candidate(10, 1, suitability=0.90),
            _make_candidate(11, 1, suitability=0.70),
            _make_candidate(12, 1, suitability=0.50),
        ],
        2: [
            _make_candidate(10, 2, suitability=0.60),
            _make_candidate(11, 2, suitability=0.88),
            _make_candidate(13, 2, suitability=0.40),
        ],
    }

    result = GlobalAssignmentOptimizer.solve_optimal_assignment(
        incidents=[inc1, inc2],
        candidates_by_incident=candidates_by_incident,
    )

    # Both incidents should be assigned
    assert 1 in result.assignments
    assert 2 in result.assignments
    # Resources must be distinct
    assert (
        result.assignments[1].resource_id != result.assignments[2].resource_id
    )


# ---------------------------------------------------------------------------
# 4. Rectangular: more incidents than resources
# ---------------------------------------------------------------------------

def test_rectangular_more_incidents_than_resources() -> None:
    """3 incidents, 2 resources — at most 2 assignments can be made."""
    incidents = [_make_incident(i) for i in (1, 2, 3)]
    candidates_by_incident: dict[int, list[DecisionCandidateDTO]] = {
        1: [_make_candidate(10, 1, suitability=0.80)],
        2: [_make_candidate(10, 2, suitability=0.70), _make_candidate(11, 2, suitability=0.60)],
        3: [_make_candidate(11, 3, suitability=0.90)],
    }

    result = GlobalAssignmentOptimizer.solve_optimal_assignment(
        incidents=incidents,
        candidates_by_incident=candidates_by_incident,
    )

    assert len(result.assignments) <= 2
    # All used resource IDs are unique
    used_resources = [c.resource_id for c in result.assignments.values()]
    assert len(used_resources) == len(set(used_resources))


# ---------------------------------------------------------------------------
# 5. Competing priorities — CRITICAL should win the best resource
# ---------------------------------------------------------------------------

def test_competing_priorities_critical_wins_best_resource() -> None:
    """
    Replicates the original test but uses the new OptimizationResult API.

    Two incidents share the same two ambulances.
    Ambulance A1 is best for Inc-102 (nearer), but Inc-101 is CRITICAL.
    The global optimizer must resolve this: CRITICAL incident (101) gets A1.
    """
    inc1 = _make_incident(101, severity="CRITICAL")
    inc2 = _make_incident(102, severity="MEDIUM")

    cand_inc1_amb1 = _make_candidate(1, 101, suitability=0.90)
    cand_inc1_amb2 = _make_candidate(2, 101, suitability=0.35)
    cand_inc2_amb1 = _make_candidate(1, 102, suitability=0.94)
    cand_inc2_amb2 = _make_candidate(2, 102, suitability=0.70)

    result = GlobalAssignmentOptimizer.solve_optimal_assignment(
        incidents=[inc1, inc2],
        candidates_by_incident={
            101: [cand_inc1_amb1, cand_inc1_amb2],
            102: [cand_inc2_amb1, cand_inc2_amb2],
        },
    )

    # CRITICAL incident gets Amb 1 (priority weight tips global cost)
    assert result.assignments[101].resource_id == 1
    assert result.assignments[102].resource_id == 2


# ---------------------------------------------------------------------------
# 6. Brute-force comparison on small cases
# ---------------------------------------------------------------------------

def _brute_force_optimal(
    incident_ids: list[int],
    resource_ids: list[int],
    suitability_map: dict[tuple[int, int], float],
) -> dict[int, int]:
    """Exhaustive search over all permutations for small matrices."""
    best_score = -1.0
    best_assignment: dict[int, int] = {}

    for perm in itertools.permutations(resource_ids, len(incident_ids)):
        score = sum(
            suitability_map.get((inc_id, res_id), 0.0)
            for inc_id, res_id in zip(incident_ids, perm, strict=False)
        )
        if score > best_score:
            best_score = score
            best_assignment = dict(zip(incident_ids, perm, strict=False))

    return best_assignment


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_brute_force_comparison_small_matrix(seed: int) -> None:
    """For 3 incidents × 4 resources, scipy result must match brute force."""
    import random

    rng = random.Random(seed)
    n_incidents = 3
    n_resources = 4
    incident_ids = list(range(1, n_incidents + 1))
    resource_ids = list(range(10, 10 + n_resources))

    suitability_map: dict[tuple[int, int], float] = {
        (i, r): round(rng.uniform(0.1, 1.0), 3)
        for i in incident_ids
        for r in resource_ids
    }

    incidents = [_make_incident(i) for i in incident_ids]
    candidates_by_incident: dict[int, list[DecisionCandidateDTO]] = {
        i: [
            _make_candidate(r, i, suitability=suitability_map[(i, r)])
            for r in resource_ids
        ]
        for i in incident_ids
    }

    result = GlobalAssignmentOptimizer.solve_optimal_assignment(
        incidents=incidents,
        candidates_by_incident=candidates_by_incident,
    )

    scipy_score = sum(
        suitability_map[(inc_id, cand.resource_id)]
        for inc_id, cand in result.assignments.items()
    )

    brute = _brute_force_optimal(incident_ids, resource_ids, suitability_map)
    brute_score = sum(suitability_map[(i, r)] for i, r in brute.items())

    # Allow tiny floating-point tolerance
    assert abs(scipy_score - brute_score) < 1e-6, (
        f"seed={seed}: scipy={scipy_score:.4f}, brute={brute_score:.4f}"
    )


# ---------------------------------------------------------------------------
# 7. Policy metadata always present
# ---------------------------------------------------------------------------

def test_result_always_has_policy_used() -> None:
    inc = _make_incident(1)
    cand = _make_candidate(10, 1)
    result = GlobalAssignmentOptimizer.solve_optimal_assignment(
        incidents=[inc],
        candidates_by_incident={1: [cand]},
    )
    assert hasattr(result, "policy_used")
    assert isinstance(result.policy_used, str)
    assert len(result.policy_used) > 0


def test_fallback_reason_is_none_when_scipy_succeeds() -> None:
    inc = _make_incident(1)
    cand = _make_candidate(10, 1)
    result = GlobalAssignmentOptimizer.solve_optimal_assignment(
        incidents=[inc],
        candidates_by_incident={1: [cand]},
    )
    # When scipy is available and succeeds, fallback_reason must be None
    if result.policy_used == "scipy_lsa":
        assert result.fallback_reason is None


# ---------------------------------------------------------------------------
# 8. Greedy fallback path (monkeypatch scipy to simulate unavailability)
# ---------------------------------------------------------------------------

def test_greedy_fallback_used_when_scipy_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate scipy being unavailable — greedy fallback must produce valid output."""
    import app.modules.ai.decision_engine.optimizer as opt_module

    monkeypatch.setattr(opt_module, "_SCIPY_AVAILABLE", False)

    inc = _make_incident(1, severity="HIGH")
    cand = _make_candidate(10, 1, suitability=0.80)

    result = GlobalAssignmentOptimizer.solve_optimal_assignment(
        incidents=[inc],
        candidates_by_incident={1: [cand]},
    )

    assert result.policy_used == "greedy_fallback"
    assert result.fallback_reason == "scipy_not_installed"
    assert result.assignments[1].resource_id == 10


def test_greedy_fallback_competing_priorities(monkeypatch: pytest.MonkeyPatch) -> None:
    """Greedy fallback must also assign non-overlapping resources."""
    import app.modules.ai.decision_engine.optimizer as opt_module

    monkeypatch.setattr(opt_module, "_SCIPY_AVAILABLE", False)

    inc1 = _make_incident(1, severity="CRITICAL")
    inc2 = _make_incident(2, severity="LOW")

    result = GlobalAssignmentOptimizer.solve_optimal_assignment(
        incidents=[inc1, inc2],
        candidates_by_incident={
            1: [_make_candidate(10, 1, suitability=0.95), _make_candidate(11, 1, suitability=0.50)],
            2: [_make_candidate(10, 2, suitability=0.70), _make_candidate(11, 2, suitability=0.60)],
        },
    )

    used = [c.resource_id for c in result.assignments.values()]
    assert len(used) == len(set(used)), "Greedy fallback assigned same resource twice"
