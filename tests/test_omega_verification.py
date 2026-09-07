from app.models import (
    Claim,
    CouncilStage,
    Evidence,
    SpecialistResult,
    VerificationStatus,
)
from app.verification import EvidenceVerifier


def evidence(url, provider):
    return Evidence(source=url, provider=provider)


def result(provider, claims=None, success=True, error=None):
    return SpecialistResult(provider=provider, role="test", task="q", claims=claims or [], success=success, error=error)


def test_cross_examination_never_promotes_consensus_to_verified():
    verifier = EvidenceVerifier()
    c1 = Claim(provider="a", statement="same", evidence=[evidence("https://a.example/1", "a"), evidence("https://b.example/1", "a")])
    c2 = Claim(provider="b", statement="same", evidence=[evidence("https://c.example/1", "b"), evidence("https://d.example/1", "b")])
    claims = verifier.verify([result("a", [c1]), result("b", [c2])])
    assert all(c.verification == VerificationStatus.CORROBORATED for c in claims)
    assert all(c.verification != VerificationStatus.VERIFIED for c in claims)


def test_explicit_contradiction_produces_cross_examination_finding():
    verifier = EvidenceVerifier()
    claim = Claim(provider="a", statement="x", contradictions=["provider b disputes x"])
    findings = verifier.cross_examine([result("a", [claim])], [claim])
    assert any(f.stage == CouncilStage.CROSS_EXAMINE and f.kind == "explicit_contradiction" for f in findings)


def test_failed_specialist_produces_evidence_gap_finding():
    verifier = EvidenceVerifier()
    findings = verifier.cross_examine([result("a", success=False, error="timeout")], [])
    assert any(f.evidence_gap and f.provider == "a" for f in findings)


def test_stress_test_caps_confidence_for_weak_evidence_states():
    verifier = EvidenceVerifier()
    claims = [
        Claim(provider="a", statement="u", verification=VerificationStatus.UNSUPPORTED),
        Claim(provider="b", statement="s", verification=VerificationStatus.STALE),
        Claim(provider="c", statement="d", verification=VerificationStatus.DISPUTED),
        Claim(provider="d", statement="v", verification=VerificationStatus.UNVERIFIABLE),
    ]
    findings = verifier.stress_test(claims, [])
    ceilings = [f.confidence_ceiling for f in findings if f.confidence_ceiling is not None]
    assert ceilings and min(ceilings) <= 0.4


def test_no_semantic_contradiction_is_invented_from_plain_text_similarity():
    verifier = EvidenceVerifier()
    c1 = Claim(provider="a", statement="Revenue increased")
    c2 = Claim(provider="b", statement="Revenue growth slowed")
    findings = verifier.cross_examine([result("a", [c1]), result("b", [c2])], [c1, c2])
    assert not any(f.kind == "semantic_contradiction" for f in findings)
