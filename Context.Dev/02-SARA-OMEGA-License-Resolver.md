# SARA-OMEGA License Resolver

Policy `CTX-COMMERCIAL-RESOLVER-001` is enforced by `context_dev_resolver.py`. It evaluates authorization state, verified Terms hashes, approved scope evidence, automation rights, target-site rights, and ZDR requirements before any future vendor adapter can execute.

Every applicable gate must pass. Denials use explicit codes and are never silently downgraded. The pending-MSA state has no credentials and no active Context.dev transport. TypeScript under `src/` provides portable contracts; Railway enforcement is Python.
