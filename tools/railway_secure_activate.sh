#!/usr/bin/env bash
set -euo pipefail

# SARA-OMEGA V.3.2.1 Railway secure activation.
# Requires a Railway CLI session linked to the intended SARA project/service.
# It never prints OWNER_TOKEN or the generated fail-safe master key.

command -v railway >/dev/null 2>&1 || { echo 'ERROR: railway CLI not found' >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo 'ERROR: python3 not found' >&2; exit 2; }
command -v openssl >/dev/null 2>&1 || { echo 'ERROR: openssl not found' >&2; exit 2; }

railway status --json >/dev/null

VARIABLE_JSON="$(railway variable list --json)"
export VARIABLE_JSON

has_variable() {
  local key="$1"
  KEY="$key" python3 - <<'PY'
import json, os, sys
key=os.environ['KEY']
try:
    doc=json.loads(os.environ['VARIABLE_JSON'])
except Exception:
    sys.exit(2)

def found(v):
    if isinstance(v, dict):
        if key in v:
            return True
        for name_field in ('name','key','variable'):
            if v.get(name_field) == key:
                return True
        return any(found(x) for x in v.values())
    if isinstance(v, list):
        return any(found(x) for x in v)
    return False
sys.exit(0 if found(doc) else 1)
PY
}

if ! has_variable OWNER_TOKEN; then
  echo 'ERROR: OWNER_TOKEN is not configured in the linked Railway service.' >&2
  echo 'Refusing to generate or rotate the owner credential automatically.' >&2
  exit 3
fi

if ! has_variable SARA_FAILSAFE_MASTER_KEY_HEX && ! has_variable SARA_FAILSAFE_MASTER_KEY_B64; then
  FAILSAFE_KEY="$(openssl rand -hex 64)"
  printf '%s' "$FAILSAFE_KEY" | railway variable set SARA_FAILSAFE_MASTER_KEY_HEX --stdin --skip-deploys >/dev/null
  unset FAILSAFE_KEY
  echo 'Installed new SARA fail-safe master key in Railway variables (value not displayed).'
else
  echo 'Existing SARA fail-safe master key retained.'
fi

railway variable set \
  SARA_FAILSAFE_REQUIRED=true \
  SARA_FAILSAFE_ROOT=/data/sara-failsafe \
  SARA_FAILSAFE_REQUIRE_DEDICATED_MOUNT=true \
  SARA_FAILSAFE_MIN_FREE_BYTES=67108864 \
  --skip-deploys >/dev/null

echo 'Installed fail-safe production variables.'

VOLUME_JSON="$(railway volume list --json 2>/dev/null || printf '[]')"
export VOLUME_JSON
if python3 - <<'PY'
import json, os, sys
try:
    doc=json.loads(os.environ['VOLUME_JSON'])
except Exception:
    sys.exit(1)

def has_data_mount(v):
    if isinstance(v, dict):
        for k, x in v.items():
            nk=str(k).lower().replace('_','')
            if nk in {'mountpath','mount'} and x == '/data':
                return True
        return any(has_data_mount(x) for x in v.values())
    if isinstance(v, list):
        return any(has_data_mount(x) for x in v)
    return False
sys.exit(0 if has_data_mount(doc) else 1)
PY
then
  echo 'Existing Railway volume mounted at /data retained.'
else
  railway volume add --mount-path /data >/dev/null
  echo 'Created Railway persistent volume mounted at /data.'
fi

railway service redeploy -y >/dev/null
echo 'Requested Railway redeploy through SARA-OMEGA V.3.2.1 production bootstrap.'
echo 'After the service boots again, check /health/production-acceptance.'
echo 'A subsequent restart/redeploy is required for cross-boot persistence proof.'
