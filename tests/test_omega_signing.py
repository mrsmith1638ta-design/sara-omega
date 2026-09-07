import inspect

import pytest

from app.models import SignatureRecord
from app.signing import DualSigner, ExternalHttpSigner, SigningError


class FakeSigner:
    def __init__(self, algorithm, *, verified=True, fail=False):
        self.algorithm = algorithm
        self.verified = verified
        self.fail = fail
        self.digests = []

    async def sign(self, digest: bytes) -> SignatureRecord:
        self.digests.append(digest)
        if self.fail:
            raise SigningError("signer_unavailable")
        return SignatureRecord(
            algorithm=self.algorithm,
            key_id=f"{self.algorithm}-key",
            signature_b64="c2ln",
            signer="fake",
        )

    async def verify(self, digest: bytes, signature: SignatureRecord) -> bool:
        self.digests.append(digest)
        return self.verified


def test_dual_signer_requires_both_algorithms():
    with pytest.raises(SigningError):
        DualSigner(FakeSigner("Ed25519"), None)
    with pytest.raises(SigningError):
        DualSigner(None, FakeSigner("ML-DSA"))


@pytest.mark.asyncio
async def test_both_signers_receive_exact_same_digest():
    ed = FakeSigner("Ed25519")
    ml = FakeSigner("ML-DSA")
    dual = DualSigner(ed, ml)
    digest = b"same-digest"
    ed_record, ml_record = await dual.sign_and_verify(digest)
    assert ed.digests == [digest, digest]
    assert ml.digests == [digest, digest]
    assert ed_record.verified and ml_record.verified


@pytest.mark.asyncio
async def test_failed_verification_fails_closed():
    dual = DualSigner(FakeSigner("Ed25519"), FakeSigner("ML-DSA", verified=False))
    with pytest.raises(SigningError, match="signature_verification_failed"):
        await dual.sign_and_verify(b"digest")


def test_external_signer_has_no_private_key_parameter():
    parameters = inspect.signature(ExternalHttpSigner.__init__).parameters
    assert all("private" not in name.lower() for name in parameters)


def test_signature_record_and_errors_do_not_expose_auth_token():
    token = "ultra-secret-token"
    signer = ExternalHttpSigner(
        algorithm="Ed25519",
        url="https://signer.invalid",
        key_id="public-id",
        token=token,
        timeout_seconds=0.01,
    )
    assert token not in repr(signer)
    record = SignatureRecord(algorithm="Ed25519", key_id="public-id", signature_b64="c2ln")
    assert token not in str(record.model_dump())


def test_from_env_fails_closed_without_signer_configuration(monkeypatch):
    for name in (
        "SARA_ED25519_SIGNER_URL", "SARA_ED25519_KEY_ID", "SARA_ED25519_SIGNER_TOKEN",
        "SARA_ML_DSA_SIGNER_URL", "SARA_ML_DSA_KEY_ID", "SARA_ML_DSA_SIGNER_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SigningError, match="signer_configuration_incomplete"):
        DualSigner.from_env()
