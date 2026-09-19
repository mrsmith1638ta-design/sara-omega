# SARA Unified Build Report

Build date: 2026-09-15T23:07:00.632991+00:00
Release: 3.2.1+unified
Python target: 3.12+

Verification evidence:
- pytest: 27 passed, 0 failed
- compileall: PASS
- editable install using installed toolchain with --no-build-isolation: PASS
- wheel build using installed toolchain with --no-build-isolation: PASS
- CLI health smoke test: PASS
- API smoke: health 200; readyz 200; capabilities 200; unauthenticated recovery 401; authenticated+approved recovery 200
- source placeholder scan (TODO/TBD/FIXME/NotImplementedError under sara_unified): CLEAN
- deterministic source manifest SHA-256: de4c02f10165d2becb6983cf2604ea528286097f227ee175579076662d78d7d2

External runtime status is not asserted by this package. ROAD/SIOS adapters fail closed when configured mandatory and unavailable.
