#!/usr/bin/env bash
set -euo pipefail

log(){ printf '[SARA-OMEGA V3.2] %s\n' "$*"; }
fail(){ printf '[SARA-OMEGA V3.2] ERROR: %s\n' "$*" >&2; exit 1; }

for cmd in railway python3 curl openssl; do
  command -v "$cmd" >/dev/null 2>&1 || fail "$cmd is required"
done

: "${RAILWAY_TOKEN:?RAILWAY_TOKEN must be supplied as a protected CI secret}"
export RAILWAY_TOKEN

TOKEN_INFO="$(curl -fsS https://backboard.railway.com/graphql/v2 \
  -H "Project-Access-Token: ${RAILWAY_TOKEN}" \
  -H 'Content-Type: application/json' \
  --data '{"query":"query { projectToken { projectId environmentId } }"}')"
export TOKEN_INFO
read -r PROJECT_ID ENV_ID < <(python3 - <<'PY'
import json, os, sys
try:
    d=json.loads(os.environ['TOKEN_INFO'])['data']['projectToken']
    print(d['projectId'], d['environmentId'])
except Exception:
    sys.exit(1)
PY
) || fail "Railway project token could not resolve project/environment"

railway link --project "$PROJECT_ID" --environment "$ENV_ID" >/dev/null

SERVICES_JSON="$(railway service list --json)"
export SERVICES_JSON
SERVICE="$(python3 - <<'PY'
import json, os, sys
raw=json.loads(os.environ['SERVICES_JSON'])

def objects(v):
    out=[]
    if isinstance(v, list):
        for x in v: out += objects(x)
    elif isinstance(v, dict):
        if isinstance(v.get('id'), str) and isinstance(v.get('name'), str):
            out.append(v)
        for x in v.values(): out += objects(x)
    return out

seen={}
for o in objects(raw):
    seen[o['id']]=o
items=list(seen.values())
if not items:
    sys.exit(1)
if len(items)==1:
    print(items[0]['name']); sys.exit(0)

def blob(o):
    return json.dumps(o, sort_keys=True).lower()

def score(o):
    n=o['name'].lower(); b=blob(o); s=0
    if 'mrsmith1638ta-design/sara-omega' in b or 'sara-omega' in b: s += 20
    if n in {'sara-omega','sara omega'}: s += 15
    if 'sara' in n and 'omega' in n: s += 10
    if 'sara' in n: s += 3
    return s
ranked=sorted(((score(o),o) for o in items), key=lambda x:x[0], reverse=True)
if not ranked or ranked[0][0] <= 0 or (len(ranked)>1 and ranked[0][0] == ranked[1][0]):
    sys.exit(2)
print(ranked[0][1]['name'])
PY
)" || fail "Could not uniquely identify the SARA OMEGA Railway service"

railway service "$SERVICE" >/dev/null
log "Target resolved: project=$PROJECT_ID environment=$ENV_ID service=$SERVICE"

DOMAIN_JSON="$(railway domain list --service "$SERVICE" --environment "$ENV_ID" --project "$PROJECT_ID" --json 2>/dev/null || printf '[]')"
export DOMAIN_JSON
DOMAIN="$(python3 - <<'PY'
import json, os
try: d=json.loads(os.environ['DOMAIN_JSON'])
except Exception: d=[]
vals=[]
def walk(v):
    if isinstance(v, dict):
        for k,x in v.items():
            if isinstance(x,str) and any(t in k.lower() for t in ('domain','host','url')):
                vals.append(x)
            walk(x)
    elif isinstance(v,list):
        for x in v: walk(x)
walk(d)
for v in vals:
    v=v.replace('https://','').replace('http://','').strip('/ ')
    if '.' in v:
        print(v); break
PY
)"

check_acceptance(){
  [ -n "$DOMAIN" ] || return 1
  BODY="$(curl -fsS --max-time 15 "https://${DOMAIN}/health/production-acceptance" 2>/dev/null || true)"
  [ -n "$BODY" ] || return 1
  BODY="$BODY" python3 - <<'PY'
import json, os, sys
try:
    d=json.loads(os.environ['BODY'])
except Exception:
    sys.exit(1)
accepted = d.get('accepted') is True or d.get('production_accepted') is True or d.get('ready') is True
sys.exit(0 if accepted else 1)
PY
}

if check_acceptance; then
  log "Railway production acceptance is already green; no changes required."
  printf '{"project_id":"%s","environment_id":"%s","service":"%s","domain":"%s","status":"already_accepted"}\n' "$PROJECT_ID" "$ENV_ID" "$SERVICE" "$DOMAIN" > railway-activation-report.json
  exit 0
fi

VARIABLE_JSON="$(railway variable list --service "$SERVICE" --environment "$ENV_ID" --json)"
export VARIABLE_JSON
has_variable(){
  KEY="$1" python3 - <<'PY'
import json, os, sys
key=os.environ['KEY']
d=json.loads(os.environ['VARIABLE_JSON'])
def found(v):
    if isinstance(v, dict):
        if key in v: return True
        if any(v.get(k)==key for k in ('name','key','variable')): return True
        return any(found(x) for x in v.values())
    if isinstance(v,list): return any(found(x) for x in v)
    return False
sys.exit(0 if found(d) else 1)
PY
}

has_variable OWNER_TOKEN || fail "OWNER_TOKEN is missing in Railway; refusing to invent/rotate owner authority"

if ! has_variable SARA_FAILSAFE_MASTER_KEY_HEX && ! has_variable SARA_FAILSAFE_MASTER_KEY_B64; then
  FAILSAFE_KEY="$(openssl rand -hex 64)"
  printf '%s' "$FAILSAFE_KEY" | railway variable set SARA_FAILSAFE_MASTER_KEY_HEX --stdin --skip-deploys --service "$SERVICE" --environment "$ENV_ID" >/dev/null
  unset FAILSAFE_KEY
  log "Generated and installed a new fail-safe master key without printing it"
else
  log "Existing fail-safe master key retained"
fi

railway variable set \
  SARA_FAILSAFE_REQUIRED=true \
  SARA_FAILSAFE_ROOT=/data/sara-failsafe \
  SARA_FAILSAFE_REQUIRE_DEDICATED_MOUNT=true \
  SARA_FAILSAFE_MIN_FREE_BYTES=67108864 \
  --skip-deploys --service "$SERVICE" --environment "$ENV_ID" >/dev/null
log "Production fail-safe variables installed"

VOLUME_JSON="$(railway volume list --service "$SERVICE" --environment "$ENV_ID" --project "$PROJECT_ID" --json 2>/dev/null || printf '[]')"
export VOLUME_JSON
if python3 - <<'PY'
import json, os, sys
try: d=json.loads(os.environ['VOLUME_JSON'])
except Exception: sys.exit(1)
def ok(v):
    if isinstance(v,dict):
        for k,x in v.items():
            if k.lower().replace('_','') in {'mount','mountpath'} and x == '/data': return True
        return any(ok(x) for x in v.values())
    if isinstance(v,list): return any(ok(x) for x in v)
    return False
sys.exit(0 if ok(d) else 1)
PY
then
  log "Persistent /data volume already present"
else
  railway volume add --service "$SERVICE" --environment "$ENV_ID" --project "$PROJECT_ID" --mount-path /data --json >/dev/null
  log "Created persistent Railway volume at /data"
fi

wait_deployment(){
  for _ in $(seq 1 90); do
    DEP="$(railway deployment list --service "$SERVICE" --environment "$ENV_ID" --limit 1 --json 2>/dev/null || printf '[]')"
    STATUS="$(DEP="$DEP" python3 - <<'PY'
import json,os
try:d=json.loads(os.environ['DEP'])
except Exception: print('UNKNOWN'); raise SystemExit
x=d[0] if isinstance(d,list) and d else d
if isinstance(x,dict): print(str(x.get('status') or x.get('state') or 'UNKNOWN').upper())
else: print('UNKNOWN')
PY
)"
    case "$STATUS" in
      SUCCESS) return 0 ;;
      FAILED|CRASHED|REMOVED) return 1 ;;
    esac
    sleep 4
  done
  return 1
}

railway redeploy --service "$SERVICE" --yes --json >/dev/null
wait_deployment || fail "Railway deployment did not reach SUCCESS"
log "First production deployment succeeded"

if ! check_acceptance; then
  railway restart --service "$SERVICE" --yes --json >/dev/null
  for _ in $(seq 1 60); do
    if check_acceptance; then break; fi
    sleep 4
  done
fi

check_acceptance || fail "Production acceptance endpoint did not become green after persistence restart"
log "Cross-boot persistence and production acceptance verified"
printf '{"project_id":"%s","environment_id":"%s","service":"%s","domain":"%s","status":"accepted"}\n' "$PROJECT_ID" "$ENV_ID" "$SERVICE" "$DOMAIN" > railway-activation-report.json
