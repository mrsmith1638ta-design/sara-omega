from __future__ import annotations

from .models import EngineeringState, ProvenanceClass, ScienceAnalysis, ScienceCalculation
from .validation import require_positive


class HTSMaglevEngine:
    domain = "maglev_hts"

    def characterize(self, *, temperature_k: float, critical_current_density: float) -> dict[str, float | str | bool | list[str]]:
        require_positive("temperature_k", temperature_k)
        require_positive("critical_current_density", critical_current_density)
        return {
            "family": "HTS",
            "temperature_k": temperature_k,
            "critical_current_density": critical_current_density,
            "flux_pinning": True,
            "passive_restoring_behavior": EngineeringState.SYSTEM_DEPENDENT.value,
            "active_control": EngineeringState.SYSTEM_DEPENDENT.value,
            "low_speed_levitation": EngineeringState.SYSTEM_DEPENDENT.value,
            "dependencies": [
                "material",
                "temperature",
                "field history",
                "guideway configuration",
                "geometry",
                "critical current density",
            ],
            "provenance_class": ProvenanceClass.EXPERIMENTAL_TECHNOLOGY.value,
        }

    def analyze_text(self, text: str) -> ScienceAnalysis:
        calculations: list[ScienceCalculation] = []
        if any(word in text.lower() for word in ("hts", "high-temperature superconductor", "flux pinning")):
            result = self.characterize(temperature_k=77.0, critical_current_density=1e8)
            calculations.append(
                ScienceCalculation(
                    equation_id="maglev.hts_characteristic",
                    variables={"B":"magnetic field", "Jc":"critical current density", "T":"temperature"},
                    units={"B":"T", "T":"K"},
                    inputs={"T":77.0, "Jc":1e8},
                    result=result,
                    provenance_class=ProvenanceClass.EXPERIMENTAL_TECHNOLOGY,
                    evidence_status="SUPPORTED",
                    assumptions=["Representative liquid-nitrogen-scale temperature for analytical comparison"],
                    limitations=["Transport-level passive restoring behavior depends on material, field history, geometry, guideway configuration, temperature, and cooling architecture"],
                    source_ids=["maglev.hts"],
                    validation_status="VALID",
                )
            )
        return ScienceAnalysis(domain=self.domain, summary="High-temperature-superconductor flux-pinning levitation analysis with configuration-dependent transport behavior explicitly scoped.", calculations=calculations, confidence=0.7 if calculations else 0.5)
