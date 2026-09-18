# SARA-OMEGA SOC 2 Incident Tabletop 001

Exercise date: 2026-09-17
Exercise type: Documentation-based tabletop
Control focus: SOC2-IR-01 / SOC2-MON-01
Status: PARTIAL — tabletop design completed; live participant exercise not yet performed

> This artifact is not evidence that a live incident exercise occurred. It is the approved scenario/runbook draft to be used for the first retained exercise.

## Scenario

Assume a privileged production credential is suspected of compromise while SARA-OMEGA continues to serve requests. At the same time, an attacker attempts replayed and malformed requests against protected routes and tries to trigger unauthorized state advancement.

## Exercise objectives

1. Detect the event through logs, alerts, provider notices, or operator observation.
2. Classify severity and assign incident commander.
3. Revoke/rotate affected credentials and sessions.
4. Freeze risky writes/releases if integrity cannot be established.
5. Preserve forensic and ROAD evidence without exposing secrets.
6. Determine whether customer/user data was accessed or affected.
7. Determine notification obligations and communications path.
8. Restore trusted operation using verified configuration and exact-source evidence.
9. Conduct post-incident review and corrective-action tracking.

## Expected control responses

- Application controls reject malformed, replayed, stale, unauthorized, or policy-invalid requests where implemented.
- Authentication alone must not create authority to advance governed state.
- Suspected credentials are rotated/revoked through the owning provider.
- Production acceptance and release status must fail closed if evidence integrity or authority is uncertain.
- Secrets must not be copied into normal ROAD evidence artifacts.
- Recovery must bind to known-good source/configuration before normal operation is declared restored.

## Injects for the live exercise

1. Provider reports a leaked token.
2. Logs show repeated unauthorized requests.
3. A release is awaiting approval during the incident.
4. One external AI/provider dependency becomes unavailable.
5. A customer asks whether their data was exposed.
6. The original operator is unavailable for 30 minutes.

## Evidence to retain after live execution

- Participants and roles
- Start/end timestamps
- Severity decision
- Timeline of actions
- Credential-revocation evidence
- Screenshots/records of alerts or simulated alerts
- Communication decision record
- Recovery validation evidence
- Lessons learned
- Corrective actions, owners, and due dates

## Current conclusion

The tabletop scenario and evidence requirements are defined, but no claim of successful exercise is permitted until the scenario is actually run with accountable participants and retained results.

`SOC2_INCIDENT_TABLETOP = DESIGNED_NOT_YET_EXECUTED`