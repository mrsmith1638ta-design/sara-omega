from __future__ import annotations

import math

from .models import ProvenanceClass, ScienceAnalysis, ScienceCalculation
from .registry import ScienceRegistry
from .validation import require_positive


class AncientEgyptEngine:
    domain = "ancient_egypt"

    def __init__(self, registry: ScienceRegistry | None = None):
        self.registry = registry or ScienceRegistry.default()

    def seked(self, base_cubits: float, height_cubits: float) -> dict[str, float | str]:
        require_positive("base_cubits", base_cubits)
        require_positive("height_cubits", height_cubits)
        seked_palms = 7.0 * ((base_cubits / 2.0) / height_cubits)
        face_angle = math.degrees(math.atan(height_cubits / (base_cubits / 2.0)))
        is_giza_reference = math.isclose(base_cubits, 440.0) and math.isclose(height_cubits, 280.0)
        return {
            "seked_palms": seked_palms,
            "face_angle_degrees": face_angle,
            "seked_provenance": (
                ProvenanceClass.HISTORICALLY_COMPATIBLE_RECONSTRUCTION.value
                if is_giza_reference else ProvenanceClass.DOCUMENTED_ANCIENT.value
            ),
            "angle_provenance": ProvenanceClass.MODERN_ENGINEERING_DERIVATION.value,
        }

    def frustum_volume(self, h: float, a: float, b: float) -> float:
        require_positive("height", h)
        require_positive("lower_side", a)
        require_positive("upper_side", b)
        return (h / 3.0) * (a * a + a * b + b * b)

    def classify_claim(self, text: str) -> str:
        lowered = text.lower()
        if "secret" in lowered or "alien" in lowered or "hidden technology" in lowered:
            return "UNVERIFIED_RECONSTRUCTION"
        return "SUPPORTED"

    def analyze_text(self, text: str) -> ScienceAnalysis:
        lowered = text.lower()
        calculations: list[ScienceCalculation] = []
        summary = "Ancient Egyptian mathematical analysis with explicit provenance boundaries."
        if "seked" in lowered or "pyramid" in lowered:
            result = self.seked(440.0, 280.0)
            calculations.append(
                ScienceCalculation(
                    equation_id="egypt.seked",
                    variables={"base":"base side", "height":"vertical height"},
                    units={"base":"cubit", "height":"cubit", "result":"palm"},
                    inputs={"base":440.0, "height":280.0},
                    result=result,
                    provenance_class=ProvenanceClass.HISTORICALLY_COMPATIBLE_RECONSTRUCTION,
                    evidence_status="SUPPORTED",
                    assumptions=["440 by 280 cubits is the conventional reconstructed Great Pyramid geometry"],
                    limitations=["No surviving Old Kingdom construction manual proves this exact procedure was used at Giza"],
                    source_ids=["egypt.rhind.p56", "egypt.giza.dimensions"],
                    validation_status="VALID",
                )
            )
        return ScienceAnalysis(domain=self.domain, summary=summary, calculations=calculations, confidence=0.85 if calculations else 0.5)
