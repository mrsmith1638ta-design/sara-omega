# OMEGA Council

OMEGA Council is SARA-OMEGA's mandatory internal reasoning path. Every request traverses the full Council lifecycle whether or not any external specialist is needed.

Mandatory lifecycle:

Observe -> Map -> Evaluate -> Generate -> Cross-Examine -> Stress-Test -> Synthesize -> Govern -> Verdict -> Record

Council rules:
1. Every request traverses all ten internal stages.
2. Decompose before delegating.
3. Invoke only specialists relevant to the request; the legacy `council` flag cannot force blanket fan-out or disable the Council.
4. Preserve independent analyses when independence matters.
5. Treat provider output as claims, not truth.
6. Compare evidence, assumptions, contradictions, recency, provenance, and uncertainty.
7. Do not decide by simple majority vote or provider consensus.
8. Challenge the strongest proposed conclusion and downgrade confidence when evidence is incomplete, stale, disputed, unsupported, or unverifiable.
9. If evidence is insufficient, say so.
10. SARA synthesizes the final verdict; no specialist becomes the final authority merely by being invoked.
11. The Council is advisory only. It does not deploy, send, purchase, mutate repositories, change cloud state, or perform another external mutation.
12. Execution is a separate authenticated, governed, fail-safe plane.
13. Every durable finalized verdict is append-only and hash-chained.
14. Durable acceptance requires both Ed25519 and ML-DSA signatures over the same canonical verdict digest, successful verification of both signatures, SQLite commit, read-after-write confirmation, and chain-head confirmation.
15. Existing accepted records are immutable. Corrections are new records referencing the prior decision through `supersedes_decision_id`.
16. Missing signer configuration, signature failure, chain corruption, or durability uncertainty fails closed. Reasoning may still be returned only as explicitly non-durable and must never be represented as a durable OMEGA verdict.
17. Raw private signing keys are not stored in SARA application files or local application persistence. Signing uses externally isolated signer/KMS/HSM infrastructure.
18. ML-DSA is mandatory for durable acceptance; there is no silent downgrade.

Standard OMEGA Verdict:
Decision; Why; Confidence; Council Findings; Critical Assumption; Primary Risk;
Evidence Gaps; Next Action; Governance Disposition; Claims; Providers Used;
Council Trace; Integrity Status; Decision ID when durable.

External specialist classes currently supported by the router include Perplexity for current research/evidence, Codex for engineering/code, Cursor for repository analysis, and Data Analytics for datasets/statistics/BI. A request may use zero external specialists while still completing the entire internal Council lifecycle.

Reasoning and execution authority are intentionally separated. A Council verdict may recommend a real-world action, but execution requires a distinct authorization path and cannot be inferred from the Council's ability to reason about the action.
