# SARA-OMEGA Adaptive ATS Intelligence

## Purpose

`app/ats_intelligence.py` gives SARA-OMEGA a governed, durable ATS/recruiting-intelligence layer. It does **not** claim that an ATS can be defeated or gamed. It keeps application preparation aligned with current verified recruiting-system behavior while preserving factual resume truth.

## Controls

- ATS detection for Workday, Greenhouse, SmartRecruiters/Winston, SAP SuccessFactors, Oracle Taleo, iCIMS, Lever, Ashby, Eightfold, Phenom, Paradox, and an unknown/common-denominator profile.
- Durable vendor-change and employer/business-unit rules in `SARA_DATA_DIR/sara_omega.db`.
- Fresh, VERIFIED vendor changes from official vendor domains can become bounded tailoring overlays; unverified or stale changes cannot alter the plan.
- Provider-specific behavior expires into fail-closed revalidation after `SARA_ATS_PROFILE_MAX_AGE_HOURS` (48 hours by default). If freshness fails, SARA automatically falls back to the common-denominator parsing-safe profile until official evidence is refreshed.
- Business-unit rules never generalize to other units without explicit company-scope evidence.
- Employer rules expire after 14 days by default unless an explicit expiry is supplied.
- Mutation endpoints require a dedicated `SARA_ATS_INTELLIGENCE_AUTH_TOKEN`; owner, GPT Action, test, Railway-control, source-control, and IoT-control tokens cannot be reused.
- Mutations require idempotency keys reserved before writes; an interrupted/uncertain mutation becomes terminal `SUBMISSION_UNVERIFIED` and is never automatically retried.
- Resume tailoring selects a truthful lane and only promotes skills already supported by candidate evidence.
- Unsupported required skills remain hard gaps; they are never inserted into the resume.
- Unknown ATS systems use the strictest common-denominator parsing-safe formatting profile.
- Live attestation reports the runtime commit if Railway supplies `RAILWAY_GIT_COMMIT_SHA`/equivalent; otherwise commit state is `UNVERIFIED`.

## Production endpoints

- `GET /ats-intelligence/health`
- `GET /ats-intelligence/attestation`
- `GET /ats-intelligence/profiles`
- `POST /ats-intelligence/detect`
- `POST /ats-intelligence/tailor-plan`
- `POST /ats-intelligence/vendor-change` (separately authenticated + idempotent)
- `POST /ats-intelligence/employer-rule` (separately authenticated + idempotent)

Production must configure a dedicated, randomly generated `SARA_ATS_INTELLIGENCE_AUTH_TOKEN` that is distinct from owner, GPT Action, test, source-control, Railway-control, and IoT-control credentials. The final verifier requires this separation to be live before deployment is accepted.

## Current evidence baseline (2026-09-08)

Official documentation confirms, among other points:

- Workday resume parsing can vary with format/order, recommends avoiding image-based styles, and does not auto-fill Skills through resume parsing; Candidate Skills Match uses skills derived from the job application/resume and job requisition, with greater weight for required skills.
- SAP SuccessFactors parses resumes into candidate-profile fields and uses Textkernel; candidate profiles are separately searchable structured records.
- SmartRecruiters June 2026 release notes state Winston Match prioritizes candidate-verified experience and education data when available, using resume parsing only when needed.
- Oracle Taleo resume parsing extracts standard personal information, education, and work-experience fields.

The external ATS Intelligence Watch should continue monitoring official vendor/employer sources and ingest only verified material changes into this runtime.

## Deployment rule

The feature is not considered production-deployed until:

1. source is committed in `mrsmith1638ta-design/sara-omega`;
2. focused and existing regression tests pass;
3. the exact reviewed commit is deployed to the existing `sara-omega` Railway production service;
4. `/ats-intelligence/attestation` returns that exact commit;
5. `/health/production-acceptance` remains `production_accepted=true`.
