from __future__ import annotations

import math

from .models import ProvenanceClass, ScienceAnalysis, ScienceCalculation
from .validation import require_positive


class ClassicalGreekRomanEngine:
    domain = "classical_greek_roman"

    ORDER_HEIGHT_RATIOS = {"doric": 7.0, "ionic": 9.0, "corinthian": 9.0}

    def column_height(self, order: str, diameter: float) -> float:
        require_positive("diameter", diameter)
        key = order.lower()
        if key not in self.ORDER_HEIGHT_RATIOS:
            raise ValueError("unsupported_classical_order")
        return self.ORDER_HEIGHT_RATIOS[key] * diameter

    def eustyle_spacing(self, diameter: float, *, central: bool = False) -> float:
        require_positive("diameter", diameter)
        return (3.0 if central else 2.25) * diameter

    def semicircular_arch(self, span: float) -> dict[str, float | str]:
        require_positive("span", span)
        radius = span / 2.0
        return {
            "radius": radius,
            "arc_length": math.pi * radius,
            "provenance_class": ProvenanceClass.MODERN_ENGINEERING_DERIVATION.value,
        }

    def analyze_text(self, text: str) -> ScienceAnalysis:
        lowered = text.lower()
        calculations: list[ScienceCalculation] = []
        if any(word in lowered for word in ("column", "ionic", "doric", "corinthian", "vitruvi")):
            order = "ionic" if "ionic" in lowered else "doric" if "doric" in lowered else "corinthian" if "corinthian" in lowered else "ionic"
            diameter = 1.0
            calculations.append(
                ScienceCalculation(
                    equation_id="rome.vitruvian.column",
                    variables={"diameter":"lower column diameter"},
                    units={"diameter":"module", "result":"module"},
                    inputs={"diameter":diameter, "order":order},
                    result=self.column_height(order, diameter),
                    provenance_class=ProvenanceClass.DOCUMENTED_ANCIENT,
                    evidence_status="SUPPORTED",
                    assumptions=["Uses the curated Vitruvian modular ratio for comparative analysis"],
                    limitations=["Ancient architectural proportions vary by passage, period, monument, and interpretation"],
                    source_ids=["rome.vitruvius"],
                    validation_status="VALID",
                )
            )
        if any(word in lowered for word in ("arch", "vault", "dome")):
            calculations.append(
                ScienceCalculation(
                    equation_id="greek.pythagorean",
                    variables={"span":"arch span"},
                    units={"span":"m", "result":"m"},
                    inputs={"span":1.0},
                    result=self.semicircular_arch(1.0),
                    provenance_class=ProvenanceClass.MODERN_ENGINEERING_DERIVATION,
                    evidence_status="SUPPORTED",
                    assumptions=["Semicircular idealization"],
                    limitations=["Modern geometric analysis; not an attested universal Roman design equation"],
                    source_ids=["rome.vitruvius", "greek.euclid"],
                    validation_status="VALID",
                )
            )
        return ScienceAnalysis(domain=self.domain, summary="Greek/Roman proportional and construction geometry analysis.", calculations=calculations, confidence=0.8 if calculations else 0.5)
