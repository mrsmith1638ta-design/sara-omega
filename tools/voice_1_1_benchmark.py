from __future__ import annotations

import math


def percentile(values: list[int], percentile_value: float) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    rank = (len(ordered) - 1) * percentile_value
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    weighted = ordered[lower] * (upper - rank) + ordered[upper] * (rank - lower)
    return int(round(weighted))


def summarize_latencies(latencies_ms: list[int]) -> dict[str, int]:
    return {
        "count": len(latencies_ms),
        "p50_ms": percentile(latencies_ms, 0.50),
        "p95_ms": percentile(latencies_ms, 0.95),
        "p99_ms": percentile(latencies_ms, 0.99),
        "max_ms": max(latencies_ms) if latencies_ms else 0,
    }
