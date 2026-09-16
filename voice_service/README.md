# SARA OMEGA Piper Voice Service

This directory is a separately deployable text-to-speech renderer for SARA OMEGA. It deliberately keeps the Piper runtime and voice model outside the main SARA application image.

## Voice

- SARA profile: `sara_elegant_british_v1`
- Piper model: `en_GB-cori-high`
- Product direction: British English female presentation; professional, elegant, calm, articulate, measured and confident.

The product-character age direction is mid-30s. It is not a claim about the source speaker's real age.

## Required runtime configuration

Set both variables before startup:

```text
PIPER_MODEL_PATH=/models/en_GB-cori-high.onnx
SARA_VOICE_SERVICE_TOKEN=<strong-random-service-token>
```

Provision both model files outside Git:

```text
/models/en_GB-cori-high.onnx
/models/en_GB-cori-high.onnx.json
```

The service intentionally fails startup when the token, model, or matching model configuration is missing.

## Run

Build from the repository root:

```bash
docker build -f voice_service/Dockerfile -t sara-piper-voice:1.0.0 .
```

Run with a private model volume and service token:

```bash
docker run --rm -p 5000:5000 \
  -e PIPER_MODEL_PATH=/models/en_GB-cori-high.onnx \
  -e SARA_VOICE_SERVICE_TOKEN="$SARA_VOICE_SERVICE_TOKEN" \
  -v /secure/path/to/models:/models:ro \
  sara-piper-voice:1.0.0
```

In production, expose port 5000 only on an internal/private network. SARA core should call this service using `SARA_PIPER_SERVICE_URL` and the same secret in `SARA_PIPER_SERVICE_TOKEN`.

## Security boundary

The service has one responsibility: convert bounded text to WAV audio. It has no SARA tool access, memory access, governance authority, recovery authority, or ability to select arbitrary model paths from request input. Every synthesis request must include the configured `X-SARA-VOICE-TOKEN`.

## Licensing boundary

`piper-tts` is isolated in this service's dependency file and is not added to SARA core. Review Piper's current license and redistribution/source-notice obligations before distributing a commercial image containing the Piper runtime. Voice model licensing must also be preserved with deployed artifacts.
