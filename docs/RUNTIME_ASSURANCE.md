# SARA Runtime Assurance

SARA Runtime Assurance is the enterprise gate that sits between generated AI output and
the user-facing/rendered response.

It is designed for regulated AI workflows where output must be checked against live
evidence before it is presented as fact.

## Product Boundary

Runtime Assurance provides:

- audit receipts for each generated output decision
- evidence adapter routing for deployment, financial, medical, legal and data analytics claims
- live module truth checks for Cloud Run/module status claims
- fail-closed claim suppression for unsupported, unavailable or contradicted checkable claims

It does not claim that an AI model can never hallucinate internally. It prevents unchecked
or contradicted claims from being rendered as trusted output.

Runtime Assurance is part of the triangle expansion upgrade. Data analytics becomes an
additional specialist lane for metrics, telemetry, dashboards and dataset review, while
the runtime gate prevents analytics claims from being rendered unless an analytics adapter
or supplied dataset evidence supports them.

## API

- `GET /runtime-assurance/health`
- `GET /runtime-assurance/adapters`
- `POST /runtime-assurance/verify-output`
- `POST /runtime-assurance/receipt/verify`

`POST /runtime-assurance/verify-output` accepts:

```json
{
  "module": "sara-voice-ui",
  "output": "sara-module-registry is live in Cloud Run.",
  "context": {
    "live_module_truth": {
      "source": "cloud_run_inventory",
      "live_count": 202,
      "historical_count": 215,
      "modules": {
        "sara-module-registry": {"live": false}
      }
    }
  }
}
```

If the claim is contradicted or unsupported under fail-closed policy, the response returns
`verdict: BLOCK`, `action: suppress`, and an audit receipt.

## Attack-Vector Cross-Reference

The build includes tests for these attack vectors before completion:

- false live-module claims
- false all-module enforcement claims
- missing evidence adapter fail-open attempts
- evidence adapter contradiction
- data analytics claim without dataset or metrics evidence
- audit receipt tampering

The design follows the architecture rule that provider output is not verified fact until
SARA has checked evidence, uncertainty and governance boundaries.
