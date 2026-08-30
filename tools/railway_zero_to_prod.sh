#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="${SARA_RAILWAY_PROJECT_NAME:-SARA-OMEGA-V3.2}"
SERVICE_NAME="${SARA_RAILWAY_SERVICE_NAME:-sara-omega}"
WORKSPACE="${SARA_RAILWAY_WORKSPACE:-}"
REPO="${GITHUB_REPOSITORY:-mrsmith1638ta-design/sara-omega}"

command -v railway >/dev/null 2>&1 || { echo 'ERROR: railway CLI missing' >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo 'ERROR: python3 missing' >&2; exit 2; }
command -v openssl >/dev/null 2>&1 || { echo 'ERROR: openssl missing' >&2; exit 2; }
command -v curl >/dev/null 2>&1 || { echo 'ERROR: curl missing' >&2; exit 2; }

if [[ -z "${RAILWAY_API_TOKEN:-}" ]]; then
  echo 'ERROR: RAILWAY_API_TOKEN is not configured.' >&2
  exit 3
fi
unset RAILWAY_TOKEN || true

json_find_named_id() {
  local json="$1" name="$2"
  JSON_DOC="$json" TARGET_NAME="$name" python3 - <<'PY'
import json, os
try: doc=json.loads(os.environ['JSON_DOC'])
except Exception: raise SystemExit(1)
name=os.environ['TARGET_NAME']
def walk(v):
    if isinstance(v, dict):
        if str(v.get('name','')) == name and v.get('id'):
            print(v['id']); return True
        for x in v.values():
            if walk(x): return True
    elif isinstance(v, list):
        for x in v:
            if walk(x): return True
    return False
raise SystemExit(0 if walk(doc) else 1)
PY
}

project_id=""
projects_json="$(railway list --json 2>/dev/null || printf '[]')"
project_id="$(json_find_named_id "$projects_json" "$PROJECT_NAME" 2>/dev/null || true)"
if [[ -z "$project_id" ]]; then
  if [[ -n "$WORKSPACE" ]]; then
    init_json="$(railway init --name "$PROJECT_NAME" --workspace "$WORKSPACE" --json)"
  else
    init_json="$(railway init --name "$PROJECT_NAME" --json)"
  fi
  project_id="$(JSON_DOC="$init_json" python3 - <<'PY'
import json, os
try: d=json.loads(os.environ['JSON_DOC'])
except Exception: raise SystemExit(1)
if isinstance(d,dict) and d.get('id'): print(d['id']); raise SystemExit
for k in ('projectId','project_id'):
    if isinstance(d,dict) and d.get(k): print(d[k]); raise SystemExit
raise SystemExit(1)
PY
)"
  echo "Created Railway project: $PROJECT_NAME"
else
  railway link --project "$project_id" >/dev/null
  echo "Using existing Railway project: $PROJECT_NAME"
fi

railway link --project "$project_id" >/dev/null 2>&1 || true

services_json="$(railway service list --json 2>/dev/null || printf '[]')"
service_id="$(json_find_named_id "$services_json" "$SERVICE_NAME" 2>/dev/null || true)"
if [[ -z "$service_id" ]]; then
  add_json="$(railway add --service "$SERVICE_NAME" --json)"
  service_id="$(JSON_DOC="$add_json" python3 - <<'PY'
import json, os
try: d=json.loads(os.environ['JSON_DOC'])
except Exception: raise SystemExit(1)
def walk(v):
    if isinstance(v,dict):
        if v.get('id') and (v.get('name')=='sara-omega' or 'service' in ''.join(v.keys()).lower()):
            print(v['id']); return True
        for x in v.values():
            if walk(x): return True
    elif isinstance(v,list):
        for x in v:
            if walk(x): return True
    return False
raise SystemExit(0 if walk(d) else 1)
PY
 2>/dev/null || true)"
  echo "Created Railway service: $SERVICE_NAME"
else
  railway service "$SERVICE_NAME" >/dev/null 2>&1 || true
  echo "Using existing Railway service: $SERVICE_NAME"
fi

kv="$(railway variable list -s "$SERVICE_NAME" --kv 2>/dev/null || true)"
get_var() { printf '%s\n' "$kv" | sed -n "s/^$1=//p" | head -n1; }
OWNER_TOKEN="$(get_var OWNER_TOKEN)"
FAILSAFE_KEY="$(get_var SARA_FAILSAFE_MASTER_KEY_HEX)"
FAILSAFE_B64="$(get_var SARA_FAILSAFE_MASTER_KEY_B64)"

if [[ -z "$OWNER_TOKEN" ]]; then
  OWNER_TOKEN="$(openssl rand -hex 48)"
  printf '%s' "$OWNER_TOKEN" | railway variable set OWNER_TOKEN --stdin -s "$SERVICE_NAME" --skip-deploys >/dev/null
  echo 'Generated and installed OWNER_TOKEN (value masked).'
fi
if [[ -n "${GITHUB_ACTIONS:-}" ]]; then echo "::add-mask::$OWNER_TOKEN"; fi

if [[ -z "$FAILSAFE_KEY" && -z "$FAILSAFE_B64" ]]; then
  FAILSAFE_KEY="$(openssl rand -hex 64)"
  printf '%s' "$FAILSAFE_KEY" | railway variable set SARA_FAILSAFE_MASTER_KEY_HEX --stdin -s "$SERVICE_NAME" --skip-deploys >/dev/null
  echo 'Generated and installed fail-safe master key (value masked).'
fi
if [[ -n "${GITHUB_ACTIONS:-}" && -n "$FAILSAFE_KEY" ]]; then echo "::add-mask::$FAILSAFE_KEY"; fi
if [[ -n "${GITHUB_ACTIONS:-}" && -n "$FAILSAFE_B64" ]]; then echo "::add-mask::$FAILSAFE_B64"; fi

railway variable set -s "$SERVICE_NAME" --skip-deploys \
  SARA_FAILSAFE_REQUIRED=true \
  SARA_FAILSAFE_ROOT=/data/sara-failsafe \
  SARA_FAILSAFE_REQUIRE_DEDICATED_MOUNT=true \
  SARA_FAILSAFE_MIN_FREE_BYTES=67108864 >/dev/null

volumes_json="$(railway volume list -s "$SERVICE_NAME" --json 2>/dev/null || printf '[]')"
if ! JSON_DOC="$volumes_json" python3 - <<'PY'
import json, os
try:d=json.loads(os.environ['JSON_DOC'])
except Exception: raise SystemExit(1)
def walk(v):
    if isinstance(v,dict):
        for k,x in v.items():
            if str(k).lower().replace('_','') in {'mountpath','mount'} and x == '/data': return True
        return any(walk(x) for x in v.values())
    if isinstance(v,list): return any(walk(x) for x in v)
    return False
raise SystemExit(0 if walk(d) else 1)
PY
then
  railway volume add --mount-path /data --service "$SERVICE_NAME" --json >/dev/null
  echo 'Created persistent volume at /data.'
else
  echo 'Persistent /data volume already present.'
fi

domains_json="$(railway domain list --service "$SERVICE_NAME" --json 2>/dev/null || printf '[]')"
BASE_URL="$(JSON_DOC="$domains_json" python3 - <<'PY'
import json, os, re
try:d=json.loads(os.environ['JSON_DOC'])
except Exception: raise SystemExit(1)
def strings(v):
    if isinstance(v,str): yield v
    elif isinstance(v,dict):
        for x in v.values(): yield from strings(x)
    elif isinstance(v,list):
        for x in v: yield from strings(x)
for s in strings(d):
    m=re.search(r'([a-zA-Z0-9-]+\.up\.railway\.app)', s)
    if m:
        print('https://'+m.group(1)); raise SystemExit
raise SystemExit(1)
PY
 2>/dev/null || true)"
if [[ -z "$BASE_URL" ]]; then
  domain_out="$(railway domain --service "$SERVICE_NAME" --json 2>/dev/null || railway domain --service "$SERVICE_NAME")"
  BASE_URL="$(DOMAIN_OUT="$domain_out" python3 - <<'PY'
import os,re
s=os.environ['DOMAIN_OUT']
m=re.search(r'([a-zA-Z0-9-]+\.up\.railway\.app)', s)
if not m: raise SystemExit(1)
print('https://'+m.group(1))
PY
)"
  echo 'Created Railway public domain.'
fi

echo 'Deploying SARA-OMEGA V.3.2...'
railway up --service "$SERVICE_NAME" --detach --message 'SARA-OMEGA V3.2 zero-to-production activation' >/dev/null

wait_deploy() {
  local status="" i
  for i in $(seq 1 90); do
    deployment_json="$(railway deployment list --service "$SERVICE_NAME" --json --limit 1 2>/dev/null || printf '[]')"
    status="$(JSON_DOC="$deployment_json" python3 - <<'PY'
import json,os
try:d=json.loads(os.environ['JSON_DOC'])
except Exception: print('UNKNOWN'); raise SystemExit
if isinstance(d,list) and d: print(d[0].get('status','UNKNOWN'))
elif isinstance(d,dict):
    x=d.get('deployments') or d.get('items') or []
    print((x[0] if isinstance(x,list) and x else d).get('status','UNKNOWN'))
else: print('UNKNOWN')
PY
)"
    case "$status" in SUCCESS) return 0;; FAILED|CRASHED|REMOVED) echo "Deployment failed: $status" >&2; return 1;; esac
    sleep 10
  done
  echo 'Deployment timed out.' >&2
  return 1
}
wait_deploy

for i in $(seq 1 30); do
  code="$(curl -ksS -o /tmp/acceptance.json -w '%{http_code}' "$BASE_URL/health/production-acceptance" || true)"
  [[ "$code" == "200" ]] && break
  sleep 5
done
python3 - <<'PY'
import json
p='/tmp/acceptance.json'
d=json.load(open(p))
required=['bootstrap_ready','failsafe_configured','root_on_dedicated_mount','checkpoint_self_test','chain_valid']
bad=[k for k in required if d.get(k) is not True]
if bad: raise SystemExit('First-boot acceptance failed: '+','.join(bad))
print('First-boot fail-safe acceptance PASS.')
PY

railway restart --service "$SERVICE_NAME" --yes >/dev/null
sleep 10
for i in $(seq 1 45); do
  code="$(curl -ksS -o /tmp/acceptance2.json -w '%{http_code}' "$BASE_URL/health/production-acceptance" || true)"
  if [[ "$code" == "200" ]] && python3 - <<'PY'
import json
try:d=json.load(open('/tmp/acceptance2.json'))
except Exception: raise SystemExit(1)
raise SystemExit(0 if d.get('production_accepted') is True else 1)
PY
  then break; fi
  sleep 5
done
python3 - <<'PY'
import json
d=json.load(open('/tmp/acceptance2.json'))
if d.get('production_accepted') is not True: raise SystemExit('Production acceptance did not reach true')
if d.get('persistence_observed_across_boots') is not True: raise SystemExit('Cross-boot persistence not proven')
print('Cross-boot persistence PASS.')
PY

SARA_OWNER_TOKEN="$OWNER_TOKEN" python3 tools/railway_runtime_acceptance.py "$BASE_URL" >/tmp/sara_railway_acceptance.json
printf '%s\n' "$BASE_URL" > /tmp/sara_railway_url.txt
cp /tmp/sara_railway_acceptance.json railway-activation-report.json
cp /tmp/sara_railway_url.txt railway-url.txt

echo "SARA-OMEGA V.3.2 production accepted at $BASE_URL"
