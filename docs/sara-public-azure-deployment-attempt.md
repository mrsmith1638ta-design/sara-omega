# SARA Public + ATS Azure Deployment Attempt

## Status

`AZURE_DEPLOYMENT: BLOCKED_SUBSCRIPTION_READ_ONLY`

The SARA Public + ATS runtime has been cross-referenced and packaged for Azure, but deployment could not complete from this environment because Azure rejected write operations for the active subscription.

## Attempted Target

- Resource group: `rg-sara-public-ats-eastus2-001`
- Location: `eastus2`
- Runtime: `PYTHON:3.12`
- SKU: `F1`
- App name from dry run: `sara-public-ats-38399`

## Azure Evidence

Dry run succeeded and reported a free-tier Linux Python App Service creation plan.

The real deployment failed with:

```text
ERROR: (ReadOnlyDisabledSubscription) The subscription '989ca3a8-1fd4-4ed5-a228-964c25498524' is disabled and therefore marked as read only. You cannot perform any write actions on this subscription until it is re-enabled.
```

`az account list --all` exposed only one subscription for this login, so there was no alternate writable Azure subscription available to use from this session.

## Verified Local Gates

- `python -m py_compile sara_public.py`
- `python sara_public.py --self-test`
- `python -m pytest -q tests/test_sara_public_azure_packaging.py`

## Acceptance Boundary

The runtime remains separate from SARA-OMEGA V3.2.1 production. Azure deployment is not complete, and production acceptance remains `UNVERIFIED` until this exact build is deployed, independently tested, ROAD-certified, and accepted.
