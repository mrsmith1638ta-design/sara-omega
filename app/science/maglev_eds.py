from __future__ import annotations

from .models import EngineeringState, ProvenanceClass, ScienceAnalysis, ScienceCalculation
from .validation import require_positive


class EDSMaglevEngine:
    domain = "maglev_eds"

    def characterize(self, *, speed_mps: float) -> dict[str, float | str | bool | list[str]]:
        require_positive("speed_mps", speed_mps)
        return {
            "family": "EDS",
            "speed_mps": speed_mps,
            "speed_dependent_lift": True,
            "active_control": EngineeringState.SYSTEM_DEPENDENT.value,
            "passive_restoring_behavior": EngineeringState.SYSTEM_DEPENDENT.value,
            "low_speed_levitation": EngineeringState.SYSTEM_DEPENDENT.value,
            "dependencies": [
                "guideway topology",
                "onboard magnet architecture",
                "damping method",
                "transition speed",
                "conductor/coil arrangement",
                "control strategy",
            ],
            "provenance_class": ProvenanceClass.ENGINEERING_MODEL.value,
        }

    def analyze_text(self, text: str) -> ScienceAnalysis:
        calculations: list[ScienceCalculation] = []
        if any(word in text.lower() for word in ("eds", "superconducting", "electrodynamic")):
            result = self.characterize(speed_mps=100.0)
            calculations.append(
                ScienceCalculation(
                    equation_id="maglev.eds_characteristic",
                    variables={"v":"speed", "B":"magnetic field"},
                    units={"v":"m/s", "B":"T"},
                    inputs={"v":100.0},
                    result=result,
                    provenance_class=ProvenanceClass.ENGINEERING_MODEL,
                    evidence_status="SUPPORTED",
                    assumptions=["Generic EDS family characterization"],
                    limitations=["Lift, low-speed transition, damping, restoring behavior, and control requirements depend on system-specific magnets, coils, conductors, guideway geometry, and control architecture"],
                    source_ids=["maglev.eds"],
                    validation_status="VALID",
                )
            )
        return ScienceAnalysis(domain=self.domain, summary="Superconducting/electrodynamic suspension analysis with architecture-dependent behavior explicitly scoped.", calculations=calculations, confidence=0.75 if calculations else 0.5)
