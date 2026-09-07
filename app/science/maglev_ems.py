from __future__ import annotations

import math

from .engineering import EngineeringPhysicsEngine
from .models import ProvenanceClass, ScienceAnalysis, ScienceCalculation
from .validation import require_positive


class EMSMaglevEngine:
    domain = "maglev_ems"
    MU0 = 4.0 * math.pi * 1e-7

    def simplified_lift(self, *, turns: float, current: float, area: float, gap: float) -> float:
        require_positive("turns", turns)
        require_positive("current", current)
        require_positive("area", area)
        require_positive("gap", gap)
        return self.MU0 * turns * turns * current * current * area / (4.0 * gap * gap)

    def aero_state(self, *, rho: float, cd: float, area: float, velocity: float) -> dict[str, float]:
        eng = EngineeringPhysicsEngine()
        drag = eng.drag_force(rho=rho, cd=cd, area=area, velocity=velocity)
        return {"drag_force_n": drag, "drag_power_w": drag * velocity}

    def analyze_text(self, text: str) -> ScienceAnalysis:
        lowered = text.lower()
        calculations: list[ScienceCalculation] = []
        if any(word in lowered for word in ("ems", "maglev", "levitation", "linear motor")):
            calculations.append(
                ScienceCalculation(
                    equation_id="maglev.ems_force_simplified",
                    variables={"N":"turns", "I":"current", "A":"pole area", "g":"air gap"},
                    units={"I":"A", "A":"m^2", "g":"m", "result":"N"},
                    inputs={"N":100.0, "I":10.0, "A":0.1, "g":0.01},
                    result=self.simplified_lift(turns=100.0, current=10.0, area=0.1, gap=0.01),
                    provenance_class=ProvenanceClass.ENGINEERING_MODEL,
                    evidence_status="SUPPORTED",
                    assumptions=["Idealized magnetic circuit scaling"],
                    limitations=["Not a universal exact EMS force law; ignores saturation, fringing, leakage, and controller dynamics"],
                    source_ids=["maglev.ems", "china.maglev.official"],
                    validation_status="VALID",
                )
            )
        return ScienceAnalysis(domain=self.domain, summary="Electromagnetic-suspension maglev analysis.", calculations=calculations, confidence=0.78 if calculations else 0.5)
