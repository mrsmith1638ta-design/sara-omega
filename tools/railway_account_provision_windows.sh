#!/usr/bin/env bash
set -euo pipefail

log(){ printf '[SARA-OMEGA V3.2.1] %s\n' "$*"; }
fail(){ printf '[SARA-OMEGA V3.2.1] ERROR: %s\n' "$*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROVISION_SCRIPT="$SCRIPT_DIR/railway_account_provision.sh"

[ -f "$PROVISION_SCRIPT" ] || fail "railway_account_provision.sh was not found"
command -v railway >/dev/null 2>&1 || fail "railway is required"

# The canonical provisioning script uses the Linux command name `python3`.
# On Windows, Git Bash commonly inherits Python as `python` or the Windows
# launcher as `py`. Provide a shell-local compatibility function without
# changing system PATH, creating symlinks, or weakening any acceptance gate.
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

PRODUCTION_DOMAIN="${SARA_RAILWAY_PRODUCTION_DOMAIN:-sara-omega-production.up.railway.app}"
SERVICE_NAME="${SARA_RAILWAY_SERVICE_NAME:-sara-omega}"
ENVIRONMENT_NAME="${SARA_RAILWAY_ENVIRONMENT:-production}"

# Resolve the already-live production project by its canonical public domain.
# This avoids creating or selecting a duplicate project just because a project
# display name changed. The scan is read-only and never prints secrets.
log "Resolving existing Railway production project by domain ${PRODUCTION_DOMAIN}"
ALL_PROJECTS_JSON="$(command railway list --json 2>/dev/null || printf '[]')"
export ALL_PROJECTS_JSON
PROJECT_ROWS="$(python3 - <<'PY'
import json, os
try:
    data = json.loads(os.environ['ALL_PROJECTS_JSON'])
except Exception:
    data = []
seen = set()
rows = []
def walk(v):
    if isinstance(v, dict):
        pid = v.get('id')
        name = v.get('name')
        if isinstance(pid, str) and pid and isinstance(name, str) and pid not in seen:
            seen.add(pid)
            rows.append((pid, name.replace('\t', ' ').replace('\n', ' ')))
        for x in v.values():
            walk(x)
    elif isinstance(v, list):
        for x in v:
            walk(x)
walk(data)
for pid, name in rows:
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

if [ -z "$TARGET_PROJECT_ID" ]; then
  fail "Could not resolve the existing production project for ${PRODUCTION_DOMAIN}; refusing to create or modify a duplicate project"
fi

log "Resolved production project ${TARGET_PROJECT_NAME} (${TARGET_PROJECT_ID})"
export TARGET_PROJECT_ID
FILTERED_PROJECTS_JSON="$(python3 - <<'PY'
import json, os
try:
    data = json.loads(os.environ['ALL_PROJECTS_JSON'])
except Exception:
    data = []
target = os.environ['TARGET_PROJECT_ID']
matches = []
def walk(v):
    if isinstance(v, dict):
        if v.get('id') == target:
            matches.append(v)
            return
        for x in v.values():
            walk(x)
    elif isinstance(v, list):
        for x in v:
            walk(x)
walk(data)
print(json.dumps(matches[:1]))
PY
)"
[ "$FILTERED_PROJECTS_JSON" != '[]' ] || fail "Resolved production project disappeared from Railway project list"

# Force the canonical controller to reuse the production project found above.
# It still performs all service, variable, fail-safe, deployment, and live
# acceptance checks unchanged.
export SARA_RAILWAY_PROJECT_NAME="$TARGET_PROJECT_NAME"

# Compatibility shim for Railway CLI releases where `volume add` rejects the
# `--service` argument. The controller already links the target service before
# volume creation, so removing only this redundant option preserves targeting.
railway(){
  if [ "${1:-}" = "list" ] && [ "${2:-}" = "--json" ]; then
    printf '%s\n' "$FILTERED_PROJECTS_JSON"
    return 0
  fi

  if [ "${1:-}" = "volume" ] && [ "${2:-}" = "add" ]; then
    shift 2
    args=()
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --service|-s)
          [ "$#" -ge 2 ] || fail "volume add service option is missing a value"
          shift 2
          ;;
        *)
          args+=("$1")
          shift
          ;;
      esac
    done
    command railway volume add "${args[@]}"
    return $?
  fi

  command railway "$@"
}
export -f railway

# Source in this shell so the compatibility functions remain available to every
# command inside the canonical provisioning controller.
# shellcheck source=tools/railway_account_provision.sh
source "$PROVISION_SCRIPT"

# Final target-integrity assertion: successful activation must remain attached
# to the canonical production URL, never to an accidental replacement domain.
if [ -f railway-public-url.txt ]; then
  resolved_url="$(tr -d '\r\n' < railway-public-url.txt)"
  [ "$resolved_url" = "https://${PRODUCTION_DOMAIN}" ] || \
    fail "Activation resolved ${resolved_url}, expected https://${PRODUCTION_DOMAIN}"
fi
