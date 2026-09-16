from dataclasses import dataclass
from sara_unified.evidence.claims import EpistemicStatus

@dataclass(frozen=True)
class FusionResult:
    statement: str
    status: EpistemicStatus
    contradiction_claim_ids: tuple[str,...]
    sources: tuple[str,...]

class EvidenceFusion:
    def fuse(self, claims):
        claims=list(claims)
        if not claims: return FusionResult("",EpistemicStatus.UNKNOWN,(),())
        polarities={c.polarity for c in claims}
        if len(polarities)>1:
            return FusionResult(claims[0].statement,EpistemicStatus.DISPUTED,tuple(c.claim_id for c in claims),tuple(c.source for c in claims))
        ranking=[EpistemicStatus.VERIFIED,EpistemicStatus.SUPPORTED,EpistemicStatus.INFERRED,EpistemicStatus.UNVERIFIED,EpistemicStatus.UNKNOWN,EpistemicStatus.CURRENTLY_INACCESSIBLE]
        status=next((s for s in ranking if any(c.status is s for c in claims)), EpistemicStatus.UNKNOWN)
        return FusionResult(claims[0].statement,status,(),tuple(c.source for c in claims))
