from __future__ import annotations

from typing import Any, Iterable

from .tail_attack_iv import (
    BLOCKED,
    CONJECTURAL,
    FINITE_CERTIFIED,
    PROVED,
    discrepancy_growth_snapshot,
    known_mertens_bound_catalog,
    subperiod_discrepancy_profile,
    weighted_mobius_mellin_statement,
)


def mean_obstruction_audit() -> dict[str, Any]:
    """Tail Attack V audit of the mean-component obstruction.

    The point is deliberately negative: SARA records that the desired
    near-square-root mean control is a proof-grade dependency because the
    relevant weighted Mobius transform contains 1/zeta(s).
    """
    return {
        "phase": "TAIL_ATTACK_V",
        "target": "A_N=o(sqrt(N) log N)",
        "normalized_target": "A_N^2/N=o(log^2 N)",
        "status": BLOCKED,
        "finite_status": FINITE_CERTIFIED,
        "uniform_status": BLOCKED,
        "rh_equivalence_risk": "HIGH",
        "zero_sensitive_transform": weighted_mobius_mellin_statement(),
        "mertens_bound_ladder": known_mertens_bound_catalog(),
        "audit_question": (
            "Does proving the required near-square-root mean bound import "
            "zeta-zero information strong enough to be RH-equivalent?"
        ),
        "promotion_rule": "proof_grade_dependency_required",
        "red_team_boundary": (
            "Do not treat PNT-level cancellation, zero-free-region bounds, "
            "Mobius randomness, or numerical mean decay as proof of this target."
        ),
    }


def discrepancy_growth_search(
    ns: Iterable[int] = (4, 6, 8, 10, 12),
    *,
    profile_n: int = 8,
) -> dict[str, Any]:
    """Finite discrepancy-growth search with asymptotic promotion blocked."""
    finite_rows = discrepancy_growth_snapshot(ns)
    return {
        "phase": "TAIL_ATTACK_V",
        "target": "discrepancy growth",
        "uniform_target": "D_N/N^2=o(log^2 N)",
        "finite_status": FINITE_CERTIFIED,
        "uniform_status": CONJECTURAL,
        "finite_rows": [
            {**row, "status": FINITE_CERTIFIED}
            for row in finite_rows
        ],
        "subperiod_profile": subperiod_discrepancy_profile(profile_n),
        "search_question": (
            "Can deterministic subperiod balancing or another transfer estimate "
            "prove D_N=o(N^2 log^2 N) without assuming Mobius randomness?"
        ),
        "red_team_boundary": (
            "finite subperiod patterns do not prove a uniform asymptotic; "
            "a theorem must control all sufficiently large N."
        ),
    }


def tail_attack_v_snapshot(n: int = 8) -> dict[str, Any]:
    """Tail Attack V dependency snapshot.

    Tail Attack V does not claim new RH progress by assertion. It records
    the two remaining doors after Tail Attack IV and hardens the promotion
    controls around the mean obstruction.
    """
    mean = mean_obstruction_audit()
    discrepancy = discrepancy_growth_search(profile_n=n)
    return {
        "phase": "TAIL_ATTACK_V",
        "program": "Mean Obstruction Audit + Discrepancy Growth Search",
        "dependencies": {
            "mean": {
                "status": mean["status"],
                "target": mean["normalized_target"],
                "risk": mean["rh_equivalence_risk"],
            },
            "covariance": {
                "status": PROVED,
                "target": "C_N/N=O(1)=o(log^2 N)",
                "source": "Tail Attack II covariance theorem",
            },
            "discrepancy": {
                "status": discrepancy["uniform_status"],
                "target": discrepancy["uniform_target"],
            },
        },
        "mean_obstruction_audit": mean,
        "discrepancy_growth_search": discrepancy,
        "uniform_tail_status": BLOCKED,
        "uniform_tail_certified": False,
        "proof_boundary": {
            "rh_proved": False,
            "reason": (
                "Tail Attack V audits the remaining proof dependencies; it does "
                "not certify the N-to-infinity estimate required for RH."
            ),
        },
        "next_actions": [
            "Classify the mean target as RH-equivalent, weaker, or stronger than RH if possible.",
            "Search for a discrepancy theorem or sharper transfer that avoids lcm-period growth.",
            "Reject combined tail promotion until mean and discrepancy dependencies are proved.",
        ],
    }
