from dataclasses import dataclass
@dataclass(frozen=True)
class CausalHypothesis:
    cause:str; effect:str; confounders:tuple[str,...]; evidence_required:tuple[str,...]
class CausalReasoner:
    def hypothesize(self,cause,effect,confounders=()): return CausalHypothesis(cause,effect,tuple(confounders),(f"independent evidence for {cause}->{effect}","confounder assessment"))
