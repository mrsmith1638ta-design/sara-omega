import base64
from datetime import date

import pytest

from sara_unified.evidence.audit import AuditLedger
from sara_unified.governance.asymmetric_signing import (
    DualKmsSignerClient,
    EvidenceSignature,
)
from sara_unified.governance.enforcement import (
    EnforcementProfile,
    GovernanceUnavailable,
    ProductionEnforcementBoundary,
)
from sara_unified.governance.unified_kernel import (
    ActionRequest,
    ActorIdentity,
    Decision,
    GovernancePolicy,
    SARAUnifiedGovernanceKernel,
    StateTransition,
)


class _Response:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class _SignerHttp:
    def __init__(self, backend="aws-kms"):
        self.backend = backend
        self.posts = []

    def get(self, url):
        return _Response(
            200,
            {
                "ok": True,
                "backend": self.backend,
                "private_key_exportable": False if self.backend == "aws-kms" else True,
                "key_ids": ["kms-ed", "kms-ml"],
            },
        )

    def post(self, url, *, headers, json):
        self.posts.append((url, headers, json))
        algorithm = json["algorithm"]
        signature = (algorithm + ":" + json["digest_b64"]).encode("utf-8")
        return _Response(
            200,
            {
                "algorithm": algorithm,
                "key_id": json["key_id"],
                "signature_b64": base64.b64encode(signature).decode("ascii"),
                "backend": self.backend,
            },
        )


def _request():
    return ActionRequest(
        request_id="req-kms-1",
        actor=ActorIdentity(
            actor_id="operator",
            actor_type="api",
            tenant_id="tenant-a",
            authenticated=True,
            capabilities=("thing:write",),
        ),
        action="thing.mutate",
        resource="thing:1",
        tool="thing-tool",
        jurisdiction="US",
        requested_capability="thing:write",
        transition=StateTransition(
            resource="thing:1",
            from_state="OLD",
            to_state="NEW",
            reversible=True,
            production=False,
        ),
        input_provenance_ok=True,
    )


def _policy():
    return GovernancePolicy(
        policy_id="kms-policy",
        version="1",
        allowed_actions=("thing.mutate",),
        allowed_tools=("thing-tool",),
        allowed_state_transitions=(("OLD", "NEW"),),
    )


def test_dual_kms_client_requires_hardware_backed_health_and_two_signatures():
    transport = _SignerHttp()
    client = DualKmsSignerClient(
        base_url="https://signer.internal",
        bearer_token="token",
        ed25519_key_id="kms-ed",
        ml_dsa_key_id="kms-ml",
        client=transport,
    )

    assert client.ready() is True
    signatures = client.sign_digest(b"D" * 64)

    assert [item.algorithm for item in signatures] == ["Ed25519", "ML-DSA"]
    assert all(item.backend == "aws-kms" for item in signatures)
    assert len(transport.posts) == 2
    assert all(
        post[2]["digest_b64"] == base64.b64encode(b"D" * 64).decode("ascii")
        for post in transport.posts
    )


def test_dual_kms_client_rejects_software_signer_in_production():
    client = DualKmsSignerClient(
        base_url="https://signer.internal",
        bearer_token="token",
        ed25519_key_id="kms-ed",
        ml_dsa_key_id="kms-ml",
        client=_SignerHttp(backend="seed-dev"),
    )

    assert client.ready() is False
    with pytest.raises(RuntimeError, match="hardware_backed"):
        client.sign_digest(b"D" * 64)


def test_kernel_records_dual_asymmetric_signatures_and_no_hmac_signature():
    signer = DualKmsSignerClient(
        base_url="https://signer.internal",
        bearer_token="token",
        ed25519_key_id="kms-ed",
        ml_dsa_key_id="kms-ml",
        client=_SignerHttp(),
    )
    kernel = SARAUnifiedGovernanceKernel(evidence_signer=signer)

    evidence = kernel.evaluate(_request(), _policy())

    assert evidence.decision is Decision.ALLOW
    assert evidence.signature == ""
    assert len(base64.b64decode(evidence.signing_digest_b64)) == 64
    assert [item.algorithm for item in evidence.signatures] == ["Ed25519", "ML-DSA"]
    assert all(item.backend == "aws-kms" for item in evidence.signatures)


class _BrokenSigner:
    def ready(self):
        return False

    def sign_digest(self, digest):
        raise RuntimeError("kms offline")


def test_boundary_fails_closed_when_kms_signing_authority_is_unavailable(tmp_path):
    boundary = ProductionEnforcementBoundary(
        AuditLedger(tmp_path / "audit.jsonl"),
        signing_key=None,
        evidence_signer=_BrokenSigner(),
        required=True,
        tenant_id="tenant-a",
        policy=_policy(),
    )
    profile = EnforcementProfile(
        action="thing.mutate",
        tool="thing-tool",
        capability="thing:write",
        from_state="OLD",
        to_state="NEW",
        reversible=True,
        production=False,
    )

    assert boundary.ready is False
    with pytest.raises(GovernanceUnavailable):
        boundary.authorize(
            profile=profile,
            actor_id="operator",
            actor_type="api",
            capabilities={"thing:write"},
            input_provenance_ok=True,
            resource="thing:1",
        )


def test_boundary_persists_publicly_verifiable_signature_metadata(tmp_path):
    signer = DualKmsSignerClient(
        base_url="https://signer.internal",
        bearer_token="token",
        ed25519_key_id="kms-ed",
        ml_dsa_key_id="kms-ml",
        client=_SignerHttp(),
    )
    audit = AuditLedger(tmp_path / "audit.jsonl")
    boundary = ProductionEnforcementBoundary(
        audit,
        signing_key=None,
        evidence_signer=signer,
        required=True,
        tenant_id="tenant-a",
        policy=_policy(),
    )
    profile = EnforcementProfile(
        action="thing.mutate",
        tool="thing-tool",
        capability="thing:write",
        from_state="OLD",
        to_state="NEW",
        reversible=True,
        production=False,
    )

    evidence = boundary.authorize(
        profile=profile,
        actor_id="operator",
        actor_type="api",
        capabilities={"thing:write"},
        input_provenance_ok=True,
        resource="thing:1",
    )

    records = audit._records()
    payload = records[-1]["details"]["execution_evidence"]
    assert payload["evidence_hash"] == evidence.evidence_hash
    assert len(payload["signatures"]) == 2
    assert payload["signature"] == ""
    assert {entry["backend"] for entry in payload["signatures"]} == {"aws-kms"}
