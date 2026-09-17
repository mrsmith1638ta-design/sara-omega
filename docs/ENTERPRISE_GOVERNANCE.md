# SARA GPT-Native Enterprise Governance

`app/enterprise_governance.py` installs the GPT-native enterprise governance contract as a SARA module. It does not create a second SARA application, replace ROAD, or duplicate provider infrastructure controls.

## Governing Principle

Inherit documented controls only within their verified scope. Build controls only where responsibility remains with SARA.

The resolver treats these as hard boundaries:

- Authentication is not execution authority.
- Provider certification is not SARA certification.
- Feature availability is not compliance inheritance.
- Missing evidence is not PASS.
- Audit Passport is an evidence package, not an audit opinion.

## Implemented Runtime Surface

- `GET /enterprise-governance/health`
- `POST /enterprise-governance/feature-eligibility`
- `POST /enterprise-governance/control-inheritance`
- `POST /enterprise-governance/evaluate-action`
- `GET /enterprise-governance/control-matrix/{tenant_id}`
- `POST /enterprise-governance/audit-passports`
- `GET /enterprise-governance/audit-passports/{tenant_id}/{passport_id}`

Mutation endpoints require `SARA_ENTERPRISE_GOVERNANCE_ADMIN_TOKEN`. The token must be separate from owner, GPT Action, model-sovereignty, ATS, Railway, source-control, and device-control authority tokens.

## Resolver Contract

`evaluate-action` fails closed when:

- the feature record is missing;
- feature evidence is `PARTIAL`, `BLOCKED`, `UNVERIFIED`, or `NOT_APPLICABLE`;
- feature evidence is stale;
- the requested provider/product/plan/feature/region does not exactly match an eligibility record;
- required configuration is missing;
- a feature or control exclusion applies;
- control ownership is unresolved;
- control evidence is not `PASS`;
- control review is stale;
- the actor lacks the required governance scope;
- the action requires human approval and no external approval id is present.

Only a feature-scoped `PASS` plus a matching control record, required configuration, required scopes, and any required human approval can produce `ALLOW`.

## Audit Passport Non-Claims

Every generated passport sets:

- `independent_assurance = false`
- `audit_opinion = false`
- `certification_statement = false`

Those values may change only when a real, authorized independent assurance artifact supports the claim. ROAD evidence organization does not by itself create an external audit opinion.

Passport notes are secret-redacted before storage. Provider admin keys, owner tokens, API keys, signing secrets, and similar credentials must never be emitted through GPT Action responses.

## ROAD Status

This module is source-installed and test-covered, but it is not a ROAD release by itself. Promotion to a named SARA-OMEGA release still requires the normal ROAD sequence:

`BUILD -> TEST -> SECURITY -> ADVERSARIAL -> EPISTEMIC -> GOVERNANCE -> PRIVACY -> PERFORMANCE -> RECOVERY -> MULTI-CLOUD -> ACCEPTANCE -> SIGN -> RELEASE`

SIGN cannot compensate for failed ACCEPTANCE, and RELEASE requires valid acceptance and signing evidence.

## Verification

```powershell
python -m pytest tests/test_enterprise_governance.py tests/test_chatgpt_action_gateway.py tests/test_enterprise_runtime_routes.py -q
python -m compileall -q main.py app sara_unified tools
git diff --check
```
