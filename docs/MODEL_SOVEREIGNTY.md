# SARA Model Sovereignty / Self-Modification Defense

`app/model_sovereignty.py` gives SARA-OMEGA an enforceable model-lifecycle firewall. It is designed to make unauthorized agent self-modification fail outside the agent's own reasoning.

## Security Invariants

- `INV-AI-SELF-01`: No autonomous agent may modify, train, replace, promote, or activate the model that governs its own behavior or another production service without independently authenticated, externally enforced authorization.
- `INV-AI-SELF-02`: Agent execution authority shall never imply model-lifecycle authority.
- `INV-AI-SELF-03`: Production inference accepts only cryptographically identified and authorized model artifacts.
- `INV-AI-SELF-04`: Model mutation and deployment must occur through separate principals and separate trust domains.
- `INV-AI-SELF-05`: Unauthorized model mutation triggers containment, evidence preservation, and rollback rather than continued execution.

## Enforced Operations

The firewall recognizes these sensitive model-lifecycle operations:

- `TRAIN`
- `FINE_TUNE`
- `MERGE_ADAPTER`
- `WRITE_CHECKPOINT`
- `CHANGE_MODEL_URI`
- `REGISTER_MODEL`
- `PROMOTE_MODEL`
- `SWAP_ENDPOINT`
- `RUNTIME_LOAD`

Training and checkpoint mutation requests are denied by default with `BLOCKED_PENDING_MODEL_CHANGE_AUTHORIZATION`.

Deployment/promotion requests for unknown model digests are denied with `BLOCKED_UNTRUSTED_MODEL_DIGEST`.

Runtime loading of an unknown digest is denied with `BLOCKED_UNSIGNED_MODEL_ARTIFACT`.

Runtime loading of a previously authorized digest is allowed, but this does not grant training authority, deployment authority, or agent model-lifecycle authority.

## Separate Authority

Approving a model digest requires `SARA_MODEL_SOVEREIGNTY_AUTH_TOKEN`.

This token must be distinct from:

- `OWNER_TOKEN`
- `GPT_ACTION_TOKEN`
- `TEST_TOKEN`
- `SARA_RAILWAY_CONTROL_AUTH_TOKEN`
- `SARA_SOURCE_CONTROL_AUTH_TOKEN`
- `SARA_DEVICE_CONTROL_AUTH_TOKEN`
- `SARA_ATS_INTELLIGENCE_AUTH_TOKEN`

If the dedicated token is missing or reused from another authority plane, mutation approval fails closed.

## Digest Registry

Authorized model digests can be supplied by:

- `SARA_AUTHORIZED_MODEL_DIGESTS`, as comma/space/semicolon-separated `sha256:<64 hex>` values.
- `POST /model-sovereignty/authorized-digests`, using the dedicated model-sovereignty authority token and an `Idempotency-Key`.

The HTTP approval path stores digest approvals in `sara_model_sovereignty.db` under `SARA_DATA_DIR`.

## HTTP Surface

- `GET /model-sovereignty/health`
- `GET /model-sovereignty/attestation`
- `POST /model-sovereignty/evaluate`
- `POST /model-sovereignty/authorized-digests`

The GPT Action status response also includes the model-sovereignty health block so the custom GPT can see that agent model-lifecycle authority is false.

## Acceptance Checks

Before promotion, verify:

```powershell
python -m pytest tests/test_model_sovereignty.py tests/test_chatgpt_action_gateway.py::test_chatgpt_action_gateway_reports_runtime_status -q
python -m compileall -q main.py app sara_unified tools
git diff --check
```

This module does not certify the research incident that motivated the control. It implements the SARA-side authority boundary recommended by the security analysis and should be routed through ROAD before being represented as production-certified evidence.
