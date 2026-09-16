from dataclasses import dataclass

@dataclass(frozen=True)
class JuryOpinion:
    model_id: str; conclusion: str; confidence: float; evidence_refs: list[str]
@dataclass(frozen=True)
class JuryResult:
    resolution: str; agreements: tuple[str,...]; disagreements: tuple[str,...]; unresolved_questions: tuple[str,...]
class ModelJury:
    def deliberate(self, opinions):
        opinions=list(opinions)
        if not opinions: return JuryResult("UNRESOLVED",(),(),("no opinions",))
        conclusions={o.conclusion for o in opinions}
        if len(conclusions)==1:
            refs=[set(o.evidence_refs) for o in opinions]
            independent = len({r for o in opinions for r in o.evidence_refs}) >= len(opinions)
            return JuryResult(opinions[0].conclusion if independent else "UNRESOLVED",(opinions[0].conclusion,),(),(() if independent else ("insufficient evidence independence",)))
        return JuryResult("UNRESOLVED",(),tuple(sorted(conclusions)),("additional independent evidence required",))
