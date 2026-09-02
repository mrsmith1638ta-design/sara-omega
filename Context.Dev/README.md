# Context.dev Pre-MSA Resolver — Railway Integration

This directory records the Python/Railway embedding of policy `CTX-COMMERCIAL-RESOLVER-001`.

Enforcement code lives in `context_dev_resolver.py` and is wired into `main.py`. The service exposes:

- `GET /context-dev/status` — sanitized public authorization state;
- `POST /context-dev/evaluate` — owner-only dry policy evaluation with no vendor call;
- `/health` — Context.dev policy-gate presence and blocked commercial runtime state.

The embedded state is `PENDING_WRITTEN_AUTHORIZATION`. It contains no Context.dev credentials, approved scopes, verified Terms hashes, or enabled vendor transport. Monetized and automated Context.dev use therefore fails closed.

Source creation, local implementation, testing, commit, remote deployment, production running, and production acceptance are recorded separately. None of those technical states constitutes Context.dev commercial authorization.
