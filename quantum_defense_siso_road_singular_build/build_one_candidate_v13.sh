#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="${PROJECT:-sara-soverigne-modules}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-sara-quantum-defense}"
SERVICE="${1:?usage: bash build_one_candidate_v13.sh SERVICE_NAME}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

case "$SERVICE" in
  sara-nexus-ppsim)
    DIR="$ROOT/01-sara-nexus-ppsim"
    CHECK="/v1/pqc/public-key"
    ENV_VARS="SARA_PQC_ENABLED=true"
    SECRETS="SARA_PQC_KYBER_PRIVATE_KEY=sara-pqc-kyber-private-key-native-v13:latest,SARA_PQC_DILITHIUM_PRIVATE_KEY=sara-pqc-dilithium-private-key-native-v13:latest"
    ;;
  sara-security-fabric)
    DIR="$ROOT/02-sara-security-fabric"
    CHECK="/v1/fabric/pqc-status"
    ENV_VARS="SARA_PQC_PPSIM_URL=https://sara-nexus-ppsim-i7iay5r2wq-uc.a.run.app,SARA_PQC_ROTATION_DAYS=30"
    SECRETS=""
    ;;
  sara-global-truth-protocol)
    DIR="$ROOT/03-sara-global-truth-protocol"
    CHECK="/v1/integrity/chain"
    ENV_VARS="SARA_PQC_PPSIM_URL=https://sara-nexus-ppsim-i7iay5r2wq-uc.a.run.app,SARA_INTEGRITY_CHAIN_COLLECTION=sara_integrity_chain"
    SECRETS=""
    ;;
  sara-evolution-engine)
    DIR="$ROOT/04-sara-evolution-engine"
    CHECK="/v1/quantum/fabric-status"
    ENV_VARS="SARA_PQC_PPSIM_URL=https://sara-nexus-ppsim-i7iay5r2wq-uc.a.run.app,SARA_QUANTUM_FABRIC_COLLECTION=sara_crypto_recommendations"
    SECRETS=""
    ;;
  sara-nexus-cipmu)
    DIR="$ROOT/05-sara-nexus-cipmu"
    CHECK="/v1/cipmu/enclave-status"
    ENV_VARS="SARA_CONFIDENTIAL_COMPUTING_ENABLED=true,SARA_PQC_PPSIM_URL=https://sara-nexus-ppsim-i7iay5r2wq-uc.a.run.app,SARA_ENCLAVE_PROJECT=$PROJECT"
    SECRETS=""
    ;;
  raft-node-n1|raft-node-n2|raft-node-n3)
    DIR="$ROOT/06-raft-node"
    CHECK="/v1/consensus/pqc-status"
    ENV_VARS="SARA_PQC_PPSIM_URL=https://sara-nexus-ppsim-i7iay5r2wq-uc.a.run.app,SARA_PQC_CONSENSUS_STRICT=true"
    SECRETS=""
    ;;
  *)
    echo "Unknown service: $SERVICE" >&2
    exit 2
    ;;
esac

TRAFFIC_JSON="$(gcloud run services describe "$SERVICE" --project="$PROJECT" --region="$REGION" --format=json)"
SERVING_REVISION="$(
  python3 -c 'import json,sys
d=json.load(sys.stdin)
for t in d.get("status",{}).get("traffic",[]):
    if t.get("percent")==100 and t.get("revisionName"):
        print(t["revisionName"])
        break
' <<<"$TRAFFIC_JSON"
)"

[[ -n "$SERVING_REVISION" ]] || {
  echo "Could not find a 100 percent serving revision for $SERVICE" >&2
  exit 1
}

BASE_IMAGE="$(
  gcloud run revisions describe "$SERVING_REVISION" \
    --project="$PROJECT" \
    --region="$REGION" \
    --format='value(spec.containers[0].image)'
)"

CURRENT_SA="$(
  gcloud run services describe "$SERVICE" \
    --project="$PROJECT" \
    --region="$REGION" \
    --format='value(spec.template.spec.serviceAccountName)'
)"

BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

cp "$DIR"/* "$BUILD_DIR"/
python3 - "$BUILD_DIR/Dockerfile.template" "$BUILD_DIR/Dockerfile" "$BASE_IMAGE" <<'PY'
from pathlib import Path
import sys
template, target, base = sys.argv[1:]
text = Path(template).read_text()
Path(target).write_text(text.replace("__BASE_IMAGE__", base))
PY
rm "$BUILD_DIR/Dockerfile.template"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}-quantum-v13:${STAMP}"

echo "=== BUILD $SERVICE FROM SERVING REVISION $SERVING_REVISION ==="
echo "BASE_IMAGE=$BASE_IMAGE"
gcloud builds submit "$BUILD_DIR" --project="$PROJECT" --tag="$IMAGE" --quiet

DEPLOY_ARGS=(
  run deploy "$SERVICE"
  --project="$PROJECT"
  --region="$REGION"
  --image="$IMAGE"
  --service-account="$CURRENT_SA"
  --no-traffic
  --tag=candidate
  --update-env-vars="$ENV_VARS"
  --quiet
)

if [[ -n "$SECRETS" ]]; then
  DEPLOY_ARGS+=(--update-secrets="$SECRETS")
fi

if [[ "$SERVICE" == "sara-nexus-cipmu" ]]; then
  DEPLOY_ARGS+=(--min-instances=0 --cpu=2 --memory=2Gi)
else
  DEPLOY_ARGS+=(--min-instances=0)
fi

echo "=== DEPLOY NO-TRAFFIC CANDIDATE $SERVICE ==="
gcloud "${DEPLOY_ARGS[@]}"

CANDIDATE_URL="$(
  gcloud run services describe "$SERVICE" \
    --project="$PROJECT" \
    --region="$REGION" \
    --format=json \
  | python3 -c 'import json,sys
d=json.load(sys.stdin)
for t in d.get("status",{}).get("traffic",[]):
    if t.get("tag")=="candidate":
        print(t.get("url",""))
        break
'
)"

TOKEN="$(gcloud auth print-identity-token)"

echo "=== VERIFY CANDIDATE HEALTH ==="
curl -i -sS -H "Authorization: Bearer $TOKEN" "$CANDIDATE_URL/health" | head -80

echo
echo "=== VERIFY CANDIDATE PATCH ENDPOINT $CHECK ==="
curl -i -sS -H "Authorization: Bearer $TOKEN" "$CANDIDATE_URL$CHECK" | head -120

echo
echo "Candidate URL: $CANDIDATE_URL"
echo "Candidate remains at 0 percent traffic."
echo "Shift only after verification:"
echo "gcloud run services update-traffic $SERVICE --project=$PROJECT --region=$REGION --to-tags=candidate=100 --quiet"
