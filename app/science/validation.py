from __future__ import annotations

from datetime import date


class ScienceValidationError(ValueError):
    pass


def require_positive(name: str, value: float) -> float:
    if value <= 0:
        raise ScienceValidationError(f"{name}_must_be_positive")
    return value


def provenance_for_reconstruction(*, direct_primary_source: bool) -> str:
    return "DOCUMENTED_ANCIENT" if direct_primary_source else "HISTORICALLY_COMPATIBLE_RECONSTRUCTION"


def classify_historical_claim(text: str) -> str:
    lowered = text.lower()
    unsupported_markers = ("secret", "alien", "hidden technology", "modern equation was written")
    if any(marker in lowered for marker in unsupported_markers):
        return "UNVERIFIED"
    return "SUPPORTED"


def current_claim_status(last_reviewed: date, *, max_age_days: int = 365) -> str:
    age = (date.today() - last_reviewed).days
    return "SUPPORTED" if age <= max_age_days else "CURRENTLY_INACCESSIBLE"
