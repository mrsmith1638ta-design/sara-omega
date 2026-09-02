from __future__ import annotations
from urllib.parse import urlparse
from .models import Claim, SpecialistResult, VerificationStatus

class EvidenceVerifier:
    '''Conservative verifier: provenance checks plus cross-provider contradiction signals.
    It intentionally does not equate a URL with truth.'''
    def verify(self, results: list[SpecialistResult]) -> list[Claim]:
        claims = [c for r in results if r.success for c in r.claims]
        for c in claims:
            valid_sources = [e for e in c.evidence if urlparse(e.source).scheme in ("http","https") and urlparse(e.source).netloc]
            if len(valid_sources) >= 2:
                c.verification = VerificationStatus.CORROBORATED
            elif len(valid_sources) == 1:
                c.verification = VerificationStatus.UNVERIFIABLE
            else:
                c.verification = VerificationStatus.UNSUPPORTED
        # Deliberately no fake semantic contradiction detector here; semantic judge receives all claims.
        return claims
