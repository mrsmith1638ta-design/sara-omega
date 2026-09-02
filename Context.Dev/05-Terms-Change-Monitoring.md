# Terms Change Monitoring

An **independent HTTP watcher** is the authoritative legal-change detector for Context.dev's documents. Context.dev may be a secondary monitor, but never the sole watcher for its own Terms.

Monitor at minimum Terms, Pricing, Fair Use, DPA, subprocessors, API stability/deprecation documentation, security/trust documentation, and changelog. Store normalized hashes, retrieval timestamps, response metadata, and source URLs. Redirects, DNS ambiguity, non-public destinations, retrieval failures, and oversized responses fail closed.

A material change affecting commercial rights, automation, AI agents, retention, intellectual property, downstream distribution, privacy, termination, indemnification, or authorization automatically sets `REVALIDATION_REQUIRED`. Monetized calls remain blocked until revalidation is approved.

Legal/license and technical API changes are tracked separately. Technical changes cannot silently alter legal authorization; legal changes can block execution while the API remains stable.
