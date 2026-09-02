#!/usr/bin/env bash
set -euo pipefail

log(){ printf '[SARA-OMEGA V3.2.1] %s\n' "$*"; }
fail(){ printf '[SARA-OMEGA V3.2.1] ERROR: %s\n' "$*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROVISION_SCRIPT="$SCRIPT_DIR/railway_account_provision.sh"

[ -f "$PROVISION_SCRIPT" ] || fail "railway_account_provision.sh was not found"
command -v railway >/dev/null 2>&1 || fail "railway is required"

if command -v python3 >/dev/null 2>&1; then
  log "Using python3"
elif command -v python >/dev/null 2>&1; then
  python3(){ command python "$@"; }
  export -f python3
  log "Mapped python3 to Windows/Git-Bash python"
elif command -v py >/dev/null 2>&1; then
  python3(){ command py -3 "$@"; }
  export -f python3
  log "Mapped python3 to Windows Python launcher"
else
  fail "Python 3 was not found as python3, python, or py"
fi

# Prevent Git Bash/MSYS from rewriting Linux container paths such as /data and
# /data/sara-failsafe before they reach railway.exe.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

PRODUCTION_DOMAIN="${SARA_RAILWAY_PRODUCTION_DOMAIN:-sara-omega-production.up.railway.app}"
SERVICE_NAME="${SARA_RAILWAY_SERVICE_NAME:-sara-omega}"
ENVIRONMENT_NAME="${SARA_RAILWAY_ENVIRONMENT:-production}"

log "Resolving existing Railway production project by domain ${PRODUCTION_DOMAIN}"
ALL_PROJECTS_JSON="$(command railway list --json 2>/dev/null || printf '[]')"
export ALL_PROJECTS_JSON
PROJECT_ROWS="$(python3 - <<'PY'
import json, os
try:
    data=json.loads(os.environ['ALL_PROJECTS_JSON'])
except Exception:
    data=[]
seen=set()
rows=[]
def walk(v):
    if isinstance(v,dict):
        pid=v.get('id'); name=v.get('name')
        if isinstance(pid,str) and pid and isinstance(name,str) and pid not in seen:
            seen.add(pid); rows.append((pid,name.replace('\t',' ').replace('\n',' ')))
        for x in v.values(): walk(x)
    elif isinstance(v,list):
        for x in v: walk(x)
walk(data)
for pid,name in rows:
    print(f"{pid}\t{name}")
PY
)"

TARGET_PROJECT_ID=''
TARGET_PROJECT_NAME=''
while IFS=$'\t' read -r candidate_id candidate_name; do
  [ -n "${candidate_id:-}" ] || continue
  domains="$(command railway domain list \
    --project "$candidate_id" \
    --environment "$ENVIRONMENT_NAME" \
    --service "$SERVICE_NAME" \
    --json 2>/dev/null || true)"
  if printf '%s' "$domains" | grep -Fq "$PRODUCTION_DOMAIN"; then
    TARGET_PROJECT_ID="$candidate_id"
    TARGET_PROJECT_NAME="$candidate_name"
    break
  fi
done <<< "$PROJECT_ROWS"

[ -n "$TARGET_PROJECT_ID" ] || \
  fail "Could not resolve existing production project for ${PRODUCTION_DOMAIN}; refusing all Railway writes"

log "Resolved production project ${TARGET_PROJECT_NAME} (${TARGET_PROJECT_ID})"
command railway link --project "$TARGET_PROJECT_ID" --environment "$ENVIRONMENT_NAME" >/dev/null \
  || fail "Could not link resolved production project ${TARGET_PROJECT_ID}"

# Exact project identity is now passed to the canonical provisioner. This skips
# project-name discovery/creation entirely and makes duplicate project creation
# impossible on the production activation path.
export SARA_RAILWAY_PROJECT_ID="$TARGET_PROJECT_ID"
export SARA_RAILWAY_PROJECT_NAME="$TARGET_PROJECT_NAME"
export SARA_RAILWAY_SERVICE_NAME="$SERVICE_NAME"
export SARA_RAILWAY_ENVIRONMENT="$ENVIRONMENT_NAME"

source "$PROVISION_SCRIPT"

if [ -f railway-public-url.txt ]; then
  resolved_url="$(tr -d '\r\n' < railway-public-url.txt)"
  [ "$resolved_url" = "https://${PRODUCTION_DOMAIN}" ] || \
    fail "Activation resolved ${resolved_url}, expected https://${PRODUCTION_DOMAIN}"
fi
