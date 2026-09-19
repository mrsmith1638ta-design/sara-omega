from __future__ import annotations

import math

from .models import RiemannProofStatus, RiemannResult


def mellin_pair(N: int, t: float) -> list[tuple[float, float]]:
    if N < 1:
        raise ValueError("N must be positive")
    return [(math.cos(t * math.log(k)), math.sin(t * math.log(k))) for k in range(1, N + 1)]


def smooth_basis_labels() -> list[str]:
    return ["1", "log(N/k)", "k/N", "(k/N)^2", "log(k+1)", "sqrt(k/N)", "edge_window"]


def frequency_scan_record(N: int, t_values: list[float]) -> RiemannResult:
    if N < 1:
        raise ValueError("N must be positive")
    if not t_values:
        raise ValueError("t_values cannot be empty")
    return RiemannResult(
        statement=f"Blind Mellin log-frequency scan record for N={N} over {len(t_values)} candidate frequencies.",
        status=RiemannProofStatus.NUMERICAL_EVIDENCE,
        evidence=["cos(t log k) and sin(t log k) finite basis construction"],
        limitations=[
            "Blind scan results are numerical evidence only.",
            "Known Riemann-zero ordinates must not seed the scan.",
            "Spectral coincidences do not certify an infinite theorem.",
        ],
        metadata={"N": N, "t_values": list(t_values), "basis": "mellin_log_frequency_pair"},
    )

