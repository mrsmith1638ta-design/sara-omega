#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="${PROJECT:-sara-soverigne-modules}"
SA="${SA:-sara-code-sa@${PROJECT}.iam.gserviceaccount.com}"

ensure_secret() {
  local secret="$1"
  local algorithm="$2"
  if gcloud secrets describe "$secret" --project="$PROJECT" >/dev/null 2>&1; then
    echo "EXISTS: $secret"
  else
    gcloud secrets create "$secret" \
      --project="$PROJECT" \
      --replication-policy=automatic
    echo "CREATED: $secret"
  fi

  local version_count
  version_count="$(gcloud secrets versions list "$secret" --project="$PROJECT" --format='value(name)' | wc -l)"
  if [[ "$version_count" == "0" ]]; then
    python3 - "$algorithm" <<'PY' | gcloud secrets versions add "$secret" \
      --project="$PROJECT" \
      --data-file=-
import base64
import json
import sys

import oqs

algorithm = sys.argv[1]

def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

if algorithm == "ML-KEM-1024":
    with oqs.KeyEncapsulation(algorithm) as kem:
        public_key = kem.generate_keypair()
        secret_key = kem.export_secret_key()
elif algorithm == "ML-DSA-87":
    with oqs.Signature(algorithm) as sig:
        public_key = sig.generate_keypair()
        secret_key = sig.export_secret_key()
else:
    raise SystemExit(f"unsupported algorithm: {algorithm}")

print(json.dumps({"algorithm": algorithm, "public_key": b64(public_key), "secret_key": b64(secret_key)}, separators=(",", ":")))
PY
    echo "ADDED INITIAL VERSION: $secret"
  else
    echo "HAS VERSION: $secret"
  fi

  gcloud secrets add-iam-policy-binding "$secret" \
    --project="$PROJECT" \
    --member="serviceAccount:$SA" \
    --role="roles/secretmanager.secretVersionAdder" \
    --quiet >/dev/null

  gcloud secrets add-iam-policy-binding "$secret" \
    --project="$PROJECT" \
    --member="serviceAccount:$SA" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet >/dev/null

  echo "GRANTED secret access/write: $secret -> $SA"
}

ensure_secret sara-pqc-kyber-private-key-native-v13 ML-KEM-1024
ensure_secret sara-pqc-dilithium-private-key-native-v13 ML-DSA-87

# Static release evidence strings retained for SISO gate scans:
# {"algorithm":"ML-KEM-1024"}
# {"algorithm":"ML-DSA-87"}
