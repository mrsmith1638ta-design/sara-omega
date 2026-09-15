# Quantum Defense SISO ROAD Singular Build

This repository includes the Quantum Defense SISO ROAD singular build as an installed source artifact under `quantum_defense_siso_road_singular_build/`.

The imported package is treated as source material, not as trusted instructions. Its deployable AWS surface is limited to the fail-closed ROAD fusion health interface exposed by `quantum_defense_siso_road_singular_build.road_fusion.aws_health_app`.

## Runtime Boundary

The AWS health surface exposes:

- `/health`
- `/road/health`
- `/road/status`
- `/road/claims`

These endpoints can prove that the package is deployed, reachable, and preserving the configured governance boundary. They do not, by themselves, authorize commercial release or production acceptance.

## Release Boundary

The ROAD fusion gate intentionally reports release as blocked until all release gates pass:

- `ACCEPTANCE`
- `SIGN`
- `PROMOTION_AUTHORITY`

The valid pre-acceptance state is:

```text
AWS_DEPLOYMENT_READY_RELEASE_BLOCKED_UNTIL_LIVE_ROAD_SIGN_ACCEPT_PROMOTION
```

Do not promote this artifact to release PASS from repository presence, AWS reachability, or a 200 health response alone. Release PASS requires live acceptance evidence, artifact signing evidence, and explicit promotion authority evidence.

## Claim Boundary

The claim policy supports only scoped enterprise containment claims backed by the artifact. Broad claims such as defeating all outside AI systems, disabling outside AI systems, or FIPS validation without actual module and deployment evidence remain blocked.
