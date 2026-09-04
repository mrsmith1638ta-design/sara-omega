SARA OMEGA Integrated Completion Campaign Resume Controller

Purpose
This folder contains a local resume controller for the existing SARA OMEGA completion campaign branch:

completion/campaign-20260903-170559

Use
Double-click RUN-SARA-OMEGA-RESUME.cmd or run it from a terminal inside the SARA OMEGA repository.

What it does
- Verifies it is running inside the SARA OMEGA Git repository.
- Verifies the campaign branch exists locally.
- Switches to completion/campaign-20260903-170559 when needed.
- Runs local ROAD Python compile checks.
- Runs ROAD unit tests.
- Runs live Railway health, ROAD tool discovery, get_completion_overview, and get_production_acceptance checks.
- Writes a timestamped JSON report under:

completion/campaign-20260903-170559/resume-reports

Safety rules
- It does not create Railway projects, services, environments, or domains.
- It does not deploy to Railway.
- It does not rotate, expose, print, or invent credentials.
- It does not force-push or rewrite Git history.
- It does not convert missing, blocked, partial, stale, user-asserted, or unverified evidence into PASS.

Optional
Run with -SkipLiveChecks if you only want local checks. Live production state will then be marked UNVERIFIED.
