from __future__ import annotations

import json

from app.models import Assignment, SpecialistResult
from .ancient_egypt import AncientEgyptEngine
from .classical_greek_roman import ClassicalGreekRomanEngine
from .engineering import EngineeringPhysicsEngine
from .maglev_ems import EMSMaglevEngine
from .maglev_eds import EDSMaglevEngine
from .maglev_hts import HTSMaglevEngine


_ENGINES = {
    "science_ancient_egypt": AncientEgyptEngine,
    "science_classical_greek_roman": ClassicalGreekRomanEngine,
    "science_engineering": EngineeringPhysicsEngine,
    "science_maglev_ems": EMSMaglevEngine,
    "science_maglev_eds": EDSMaglevEngine,
    "science_maglev_hts": HTSMaglevEngine,
}


class ScienceSpecialist:
    def __init__(self, provider_name: str):
        if provider_name not in _ENGINES:
            raise ValueError("unknown_science_provider")
        self.provider_name = provider_name
        self.engine = _ENGINES[provider_name]()

    async def run(self, assignment: Assignment) -> SpecialistResult:
        analysis = self.engine.analyze_text(assignment.task)
        payload = analysis.model_dump(mode="json")
        return SpecialistResult(
            provider=self.provider_name,
            role=assignment.role,
            task=assignment.task,
            answer=json.dumps(payload, sort_keys=True, separators=(",", ":")),
            claims=[],
            evidence=[],
            success=True,
            raw={"science_analysis": payload},
        )
