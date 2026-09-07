from __future__ import annotations
from urllib.parse import urlparse
from .models import Claim, CouncilChallenge, CouncilStage, SpecialistResult, VerificationStatus

class EvidenceVerifier:
    '''Conservative verifier: provenance checks plus cross-provider contradiction signals.
    It intentionally does not equate a URL with truth.'''

    def verify(self, results: list[SpecialistResult]) -> list[Claim]:
        claims = [c for r in results if r.success for c in r.claims]
        for c in claims:
            valid_sources = [
                e for e in c.evidence
                if urlparse(e.source).scheme in ("http", "https") and urlparse(e.source).netloc
            ]
            if len(valid_sources) >= 2:
                c.verification = VerificationStatus.CORROBORATED
            elif len(valid_sources) == 1:
                c.verification = VerificationStatus.UNVERIFIABLE
            else:
                c.verification = VerificationStatus.UNSUPPORTED
        return claims

    def cross_examine(
        self,
        results: list[SpecialistResult],
        claims: list[Claim],
    ) -> list[CouncilChallenge]:
        findings: list[CouncilChallenge] = []
        for result in results:
            if not result.success:
                detail = (result.error or "specialist unavailable")[:400]
                findings.append(
                    CouncilChallenge(
                        stage=CouncilStage.CROSS_EXAMINE,
                        kind="specialist_evidence_gap",
                        finding=f"{result.provider} did not return usable evidence: {detail}",
                        provider=result.provider,
                        evidence_gap=True,
                    )
                )
        for claim in claims:
            for contradiction in claim.contradictions:
                findings.append(
                    CouncilChallenge(
                        stage=CouncilStage.CROSS_EXAMINE,
                        kind="explicit_contradiction",
                        finding=contradiction[:1000],
                        provider=claim.provider,
                    )
                )
        return findings

    def stress_test(
        self,
        claims: list[Claim],
        challenges: list[CouncilChallenge],
    ) -> list[CouncilChallenge]:
        findings: list[CouncilChallenge] = []
        ceilings = {
            VerificationStatus.DISPUTED: 0.35,
            VerificationStatus.UNSUPPORTED: 0.25,
            VerificationStatus.STALE: 0.40,
            VerificationStatus.UNVERIFIABLE: 0.45,
        }
        for claim in claims:
            ceiling = ceilings.get(claim.verification)
            if ceiling is None:
                continue
            findings.append(
                CouncilChallenge(
                    stage=CouncilStage.STRESS_TEST,
                    kind="evidence_state_confidence_cap",
                    finding=(
                        f"Claim from {claim.provider} is {claim.verification.value}; "
                        f"confidence must not exceed {ceiling:.2f} without stronger evidence."
                    ),
                    provider=claim.provider,
                    confidence_ceiling=ceiling,
                    evidence_gap=claim.verification in {
                        VerificationStatus.UNSUPPORTED,
                        VerificationStatus.UNVERIFIABLE,
                    },
                )
            )
        if any(item.evidence_gap for item in challenges):
            findings.append(
                CouncilChallenge(
                    stage=CouncilStage.STRESS_TEST,
                    kind="missing_specialist_evidence",
                    finding="One or more requested specialist analyses are unavailable.",
                    confidence_ceiling=0.50,
                    evidence_gap=True,
                )
            )
        return findings
