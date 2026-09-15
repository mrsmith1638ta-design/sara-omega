#!/usr/bin/env bash
set -euo pipefail

PROJECT="sara-soverigne-modules"
REGION="us-central1"
REPO="sara-quantum-defense"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BASE="$(cd "$(dirname "$0")" && pwd)"

deploy_service() {
  local SERVICE="$1"
  local DOCKERFILE="$2"
  local CHECK="$3"

  echo ""
  echo "=== BUILDING $SERVICE ==="
  IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}-v3:${STAMP}"

  cp "$BASE/$DOCKERFILE" "$BASE/Dockerfile"
  gcloud builds submit "$BASE" --project="$PROJECT" --tag="$IMAGE"
  rm -f "$BASE/Dockerfile"

  CURRENT_SA="$(gcloud run services describe "$SERVICE" \
    --project="$PROJECT" --region="$REGION" \
    --format='value(spec.template.spec.serviceAccountName)')"

  gcloud run deploy "$SERVICE" \
    --project="$PROJECT" --region="$REGION" \
    --image="$IMAGE" \
    --service-account="$CURRENT_SA" \
    --min-instances=0 \
    --quiet

  TOKEN="$(gcloud auth print-identity-token)"
  URL="$(gcloud run services describe "$SERVICE" \
    --project="$PROJECT" --region="$REGION" \
    --format='value(status.url)')"

  curl -fsS -H "Authorization: Bearer $TOKEN" "$URL$CHECK" \
    | python3 -m json.tool | head -8 \
    && echo "PASS: $SERVICE" \
    || echo "FAIL: $SERVICE $CHECK"
}

deploy_service "sara-security-fabric"       "Dockerfile.fabric"    "/v1/fabric/pqc-status"
deploy_service "sara-global-truth-protocol" "Dockerfile.integrity" "/v1/integrity/chain"
deploy_service "sara-nexus-cipmu"           "Dockerfile.cipmu"     "/v1/cipmu/enclave-status"

echo ""
echo "=== BUILDING RAFT NODES ==="
RAFT_IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/raft-node-v3:${STAMP}"
cp "$BASE/Dockerfile.raft" "$BASE/Dockerfile"
gcloud builds submit "$BASE" --project="$PROJECT" --tag="$RAFT_IMAGE"
rm -f "$BASE/Dockerfile"

TOKEN="$(gcloud auth print-identity-token)"
for NODE in raft-node-n1 raft-node-n2 raft-node-n3; do
  CURRENT_SA="$(gcloud run services describe "$NODE" \
    --project="$PROJECT" --region="$REGION" \
    --format='value(spec.template.spec.serviceAccountName)')"
  gcloud run deploy "$NODE" \
    --project="$PROJECT" --region="$REGION" \
    --image="$RAFT_IMAGE" \
    --service-account="$CURRENT_SA" \
    --min-instances=0 \
    --quiet
  URL="$(gcloud run services describe "$NODE" \
    --project="$PROJECT" --region="$REGION" \
    --format='value(status.url)')"
  curl -fsS -H "Authorization: Bearer $TOKEN" "$URL/v1/consensus/pqc-status" \
    | python3 -m json.tool | head -8 \
    && echo "PASS: $NODE" \
    || echo "FAIL: $NODE"
done

echo ""
echo "=== QUANTUM DEFENSE V3 COMPLETE ==="
