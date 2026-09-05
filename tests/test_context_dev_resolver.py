from __future__ import annotations

import pytest

import context_dev_resolver as resolver
from context_dev_resolver import (
    AuthorizationState,
    ChangeStream,
    ContextDevPolicyDenied,
    DenialCode,
    GovernedContextDevAdapter,
    RequestContext,
    VendorLicenseState,
    classify_terms_change,
    evaluate_request,
)


def blocked_request() -> RequestContext:
    return RequestContext(
        request_id="pending-msa-test",
        monetized=True,
        automated_use=True,
        target_site_rights_valid=False,
        sensitive=True,
        requires_zdr=True,
        zdr_entitlement_verified=False,
        zdr_endpoint_verified=False,
    )


def test_pending_msa_emits_all_applicable_denials():
    decision = evaluate_request(blocked_request(), VendorLicenseState.pending_msa())
    assert decision.allowed is False
    codes = {denial.code for denial in decision.denials}
    assert codes == {
        DenialCode.COMMERCIAL_AUTHORIZATION_NOT_VERIFIED,
        DenialCode.TERMS_HASH_MISSING,
        DenialCode.AUTOMATED_USE_NOT_AUTHORIZED,
        DenialCode.SCOPE_NOT_AUTHORIZED,
        DenialCode.TARGET_SITE_RIGHTS_FAILED,
        DenialCode.ZDR_NOT_VERIFIED,
    }


def test_pending_msa_cannot_reach_vendor_transport():
    transport_calls = 0

    def transport(_payload):
        nonlocal transport_calls
        transport_calls += 1
        return {"status": 200}

    adapter = GovernedContextDevAdapter(VendorLicenseState.pending_msa, transport)
    with pytest.raises(ContextDevPolicyDenied):
        adapter.execute(blocked_request(), {"operation": "search"})
    assert transport_calls == 0


def test_material_legal_change_requires_revalidation():
    result = classify_terms_change(
        "a" * 64,
        "b" * 64,
        ["commercial rights"],
        ChangeStream.LEGAL_LICENSE,
    )
    assert result.material is True
    assert result.next_authorization_state is AuthorizationState.REVALIDATION_REQUIRED


def test_technical_change_does_not_modify_legal_authorization_state():
    result = classify_terms_change(
        "a" * 64,
        "b" * 64,
        ["commercial rights"],
        ChangeStream.TECHNICAL_API,
    )
    assert result.changed is True
    assert result.material is False
    assert result.next_authorization_state is None


def test_public_status_does_not_claim_credentials_or_vendor_transport():
    status = VendorLicenseState.pending_msa().public_status()
    assert status["commercial_authorization"] == "PENDING_WRITTEN_AUTHORIZATION"
    assert status["monetized_runtime"] == "BLOCKED"
    assert status["credentials_configured"] is False
    assert status["vendor_transport_enabled"] is False


def test_verified_label_without_scoped_evidence_still_blocks_runtime():
    state = VendorLicenseState(
        authorization_state=AuthorizationState.VERIFIED,
        authorized_scopes=frozenset(),
        stored_terms_hash="a" * 64,
        verified_terms_hash="a" * 64,
        terms_version="2026-08-20",
        reviewed_at="2026-09-02T00:00:00Z",
    )
    assert state.commercial_runtime_authorized() is False
    assert state.public_status()["monetized_runtime"] == "BLOCKED"


def test_reviewed_written_authorization_enables_required_commercial_scope():
    state = resolver.load_context_dev_license()
    status = state.public_status()

    assert state.authorization_state is AuthorizationState.VERIFIED
    assert resolver.REQUIRED_COMMERCIAL_SCOPES.issubset(state.authorized_scopes)
    assert state.commercial_runtime_authorized() is True
    assert status["commercial_authorization"] == "VERIFIED"
    assert status["monetized_runtime"] == "ALLOWED"
    assert status["production_authorization"] == "SCOPE_VERIFIED"
    assert status["credentials_configured"] is False
    assert status["vendor_transport_enabled"] is False
