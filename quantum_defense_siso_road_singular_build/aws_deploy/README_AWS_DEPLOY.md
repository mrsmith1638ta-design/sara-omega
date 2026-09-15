# SARA Quantum Defense ROAD-Fused AWS Deployment

This package includes a zero-framework Python health surface for AWS App Runner,
ECS, Lambda, or any WSGI-compatible host.

Required verification endpoints:

- `/health`
- `/road/health`
- `/road/status`
- `/road/claims`

The build embeds these grep-visible ROAD claim controls:

- defeat all rogue AI
- disables outside AI systems
- FIPS validation unless the actual crypto module and deployment are validated

Release remains blocked until AWS live acceptance, artifact signing, and
promotion authority are verified by ROAD.

