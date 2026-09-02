from app.verification import EvidenceVerifier
from app.models import *
def test_two_sources_are_correlated_not_verified():
    c=Claim(provider="x",statement="claim",evidence=[
        Evidence(source="https://a.example/x",provider="x"),
        Evidence(source="https://b.example/y",provider="x")])
    r=SpecialistResult(provider="x",role="r",task="t",claims=[c])
    out=EvidenceVerifier().verify([r])[0]
    assert out.verification == VerificationStatus.CORROBORATED
