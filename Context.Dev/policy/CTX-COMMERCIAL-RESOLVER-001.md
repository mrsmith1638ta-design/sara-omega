# CTX-COMMERCIAL-RESOLVER-001

Context.dev commercial traffic is blocked unless written authorization is `VERIFIED`, stored and current verified Terms hashes match, each required scope has approved evidence, target-site rights pass independently, and required ZDR entitlement and endpoint support are verified.

## Governing principles

1. Evidence precedes commercial authorization.
2. Public marketing does not override explicit contractual restrictions.
3. Monetized traffic fails closed unless authorization is `VERIFIED`.
4. Automated/API/MCP rights must be explicitly covered.
5. Derived customer-facing outputs must be covered.
6. Evidence and provenance retention must be covered.
7. Continuous monitoring must be covered.
8. Credentials remain server-side.
9. Target-site rights, robots directives, and terms are a separate gate.
10. Material Terms changes set `REVALIDATION_REQUIRED`.
11. Monetized calls remain blocked during revalidation.
12. Technical API and legal/license changes are tracked separately.
13. Sensitive ZDR-required processing fails closed without verified entitlement and endpoint support.
14. Authorization evidence records date, scope, source, Terms version, and SHA-256 hash.

The enforcement implementation is `context_dev_resolver.py`. It contains no Context.dev credentials or active vendor transport while the MSA is pending.
