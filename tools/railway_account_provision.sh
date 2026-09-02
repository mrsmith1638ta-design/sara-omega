#!/usr/bin/env bash
set -euo pipefail

log(){ printf '[SARA-OMEGA V3.2.1] %s\n' "$*"; }
fail(){ printf '[SARA-OMEGA V3.2.1] ERROR: %s\n' "$*" >&2; exit 1; }

for cmd in railway python3 curl openssl; do
  command -v "$cmd" >/dev/null 2>&1 || fail "$cmd is required"
done

PROJECT_NAME="${SARA_RAILWAY_PROJECT_NAME:-SARA-OMEGA-V3.2.1}"
SERVICE_NAME="${SARA_RAILWAY_SERVICE_NAME:-sara-omega}"
ENVIRONMENT_NAME="${SARA_RAILWAY_ENVIRONMENT:-production}"

log "Authenticated Railway identity"
railway whoami || fail "Railway authentication not active"

log "Looking for existing project named ${PROJECT_NAME}"
PROJECTS_JSON="$(railway list --json 2>/dev/null || printf '[]')"
export PROJECTS_JSON PROJECT_NAME
PROJECT_ID="$(python3 - <<'PY'
import json, os
try:
    data=json.loads(os.environ['PROJECTS_JSON'])
except Exception:
    data=[]
name=os.environ['PROJECT_NAME']
found=[]
def walk(v):
    if isinstance(v,dict):
        if v.get('name') == name and isinstance(v.get('id'),str):
            found.append(v['id'])
        for x in v.values(): walk(x)
    elif isinstance(v,list):
        for x in v: walk(x)
walk(data)
print(found[0] if found else '')
PY
)"

if [ -n "$PROJECT_ID" ]; then
  railway link --project "$PROJECT_ID" --environment "$ENVIRONMENT_NAME" >/dev/null
  log "Reusing project ${PROJECT_ID}"
else
  log "Creating Railway project ${PROJECT_NAME}"
  INIT_JSON="$(railway init --name "$PROJECT_NAME" --json)"
  export INIT_JSON
  PROJECT_ID="$(python3 - <<'PY'
import json, os, sys
try:
    data=json.loads(os.environ['INIT_JSON'])
except Exception:
    sys.exit(1)

def find(v):
    if isinstance(v,dict):
        for k in ('id','projectId','project_id'):
            x=v.get(k)
            if isinstance(x,str) and x:
                return x
        for x in v.values():
            y=find(x)
            if y: return y
    elif isinstance(v,list):
        for x in v:
            y=find(x)
            if y: return y
    return None
x=find(data)
if not x: sys.exit(1)
print(x)
PY
)" || fail "Could not resolve newly created Railway project ID"
  log "Created project ${PROJECT_ID}"
fi

# Ensure the production environment is selected. Newly created Railway projects
# include production by default; this is intentionally non-destructive.
railway environment "$ENVIRONMENT_NAME" >/dev/null 2>&1 || true

log "Ensuring service ${SERVICE_NAME} exists"
SERVICES_JSON="$(railway service list --json 2>/dev/null || printf '[]')"
export SERVICES_JSON SERVICE_NAME
SERVICE_EXISTS="$(python3 - <<'PY'
import json, os
try: data=json.loads(os.environ['SERVICES_JSON'])
except Exception: data=[]
name=os.environ['SERVICE_NAME']
found=False
def walk(v):
    global found
    if isinstance(v,dict):
        if v.get('name') == name:
            found=True
        for x in v.values(): walk(x)
    elif isinstance(v,list):
        for x in v: walk(x)
walk(data)
print('yes' if found else 'no')
PY
)"
if [ "$SERVICE_EXISTS" != yes ]; then
  railway add --service "$SERVICE_NAME" --json >/dev/null
  log "Created service ${SERVICE_NAME}"
fi
railway service "$SERVICE_NAME" >/dev/null

log "Installing production authority and fail-safe variables"
VARIABLES_JSON="$(railway variable list --service "$SERVICE_NAME" --json 2>/dev/null || printf '{}')"
export VARIABLES_JSON
has_variable(){
  KEY="$1" python3 - <<'PY'
import json, os, sys
key=os.environ['KEY']
try: data=json.loads(os.environ['VARIABLES_JSON'])
except Exception: data={}
def found(v):
    if isinstance(v,dict):
        if key in v: return True
        if any(v.get(k) == key for k in ('name','key','variable')): return True
        return any(found(x) for x in v.values())
    if isinstance(v,list): return any(found(x) for x in v)
    return False
sys.exit(0 if found(data) else 1)
PY
}

if ! has_variable OWNER_TOKEN; then
  OWNER_TOKEN_GENERATED="$(openssl rand -hex 48)"
  printf '%s' "$OWNER_TOKEN_GENERATED" | railway variable set OWNER_TOKEN --stdin --skip-deploys --service "$SERVICE_NAME" >/dev/null
  log "Generated owner authority token without printing it"
else
  OWNER_TOKEN_GENERATED=''
  log "Existing owner authority token retained"
fi

if ! has_variable GPT_ACTION_TOKEN; then
  GPT_ACTION_TOKEN_GENERATED="$(openssl rand -hex 48)"
  printf '%s' "$GPT_ACTION_TOKEN_GENERATED" | railway variable set GPT_ACTION_TOKEN --stdin --skip-deploys --service "$SERVICE_NAME" >/dev/null
  log "Generated dedicated GPT Action token without printing it"
else
  GPT_ACTION_TOKEN_GENERATED=''
  log "Existing dedicated GPT Action token retained"
fi

if ! has_variable SARA_FAILSAFE_MASTER_KEY_HEX && ! has_variable SARA_FAILSAFE_MASTER_KEY_B64; then
  FAILSAFE_KEY="$(openssl rand -hex 64)"
  printf '%s' "$FAILSAFE_KEY" | railway variable set SARA_FAILSAFE_MASTER_KEY_HEX --stdin --skip-deploys --service "$SERVICE_NAME" >/dev/null
  unset FAILSAFE_KEY
  log "Generated fail-safe master key without printing it"
else
  log "Existing fail-safe master key retained"
fi

railway variable set \
  SARA_FAILSAFE_REQUIRED=true \
  SARA_FAILSAFE_ROOT=/data/sara-failsafe \
  SARA_FAILSAFE_REQUIRE_DEDICATED_MOUNT=true \
  SARA_FAILSAFE_MIN_FREE_BYTES=67108864 \
  SARA_RELEASE_VERSION=3.2.1 \
  --skip-deploys --service "$SERVICE_NAME" >/dev/null

log "Ensuring persistent /data volume exists"
VOLUMES_JSON="$(railway volume list --service "$SERVICE_NAME" --json 2>/dev/null || printf '[]')"
export VOLUMES_JSON
if ! python3 - <<'PY'
import json, os, sys
try: data=json.loads(os.environ['VOLUMES_JSON'])
except Exception: sys.exit(1)
def ok(v):
    if isinstance(v,dict):
        for k,x in v.items():
            if str(k).lower().replace('_','') in {'mount','mountpath'} and x == '/data':
                return True
        return any(ok(x) for x in v.values())
    if isinstance(v,list): return any(ok(x) for x in v)
    return False
sys.exit(0 if ok(data) else 1)
PY
then
  railway volume add --service "$SERVICE_NAME" --mount-path /data --json >/dev/null
  log "Created persistent /data volume"
else
  log "Persistent /data volume already present"
fi

log "Deploying checked-out SARA-OMEGA V3.2.1 source"
railway up --service "$SERVICE_NAME" --ci

log "Waiting for successful deployment"
for _ in $(seq 1 90); do
  DEP_JSON="$(railway deployment list --service "$SERVICE_NAME" --limit 1 --json 2>/dev/null || printf '[]')"
  export DEP_JSON
  STATUS="$(python3 - <<'PY'
import json, os
try: data=json.loads(os.environ['DEP_JSON'])
except Exception:
    print('UNKNOWN'); raise SystemExit
x=data[0] if isinstance(data,list) and data else data
print(str((x.get('status') if isinstance(x,dict) else None) or (x.get('state') if isinstance(x,dict) else None) or 'UNKNOWN').upper())
PY
)"
  case "$STATUS" in
    SUCCESS) break ;;
    FAILED|CRASHED|REMOVED) fail "Railway deployment ended in ${STATUS}" ;;
  esac
  sleep 4
done
[ "$STATUS" = SUCCESS ] || fail "Railway deployment did not reach SUCCESS"

log "Ensuring Railway public domain exists"
DOMAIN_LIST="$(railway domain list --service "$SERVICE_NAME" --json 2>/dev/null || printf '[]')"
export DOMAIN_LIST
DOMAIN="$(python3 - <<'PY'
import json, os, re
try: data=json.loads(os.environ['DOMAIN_LIST'])
except Exception: data=[]
vals=[]
def walk(v):
    if isinstance(v,dict):
        for k,x in v.items():
            if isinstance(x,str) and any(t in str(k).lower() for t in ('domain','url','host')):
                vals.append(x)
            walk(x)
    elif isinstance(v,list):
        for x in v: walk(x)
walk(data)
for v in vals:
    v=re.sub(r'^https?://','',v).strip('/ ')
    if v.endswith('.up.railway.app'):
        print(v); break
PY
)"
if [ -z "$DOMAIN" ]; then
  DOMAIN_JSON="$(railway domain --service "$SERVICE_NAME" --json)"
  export DOMAIN_JSON
  DOMAIN="$(python3 - <<'PY'
import json, os, re, sys
try: data=json.loads(os.environ['DOMAIN_JSON'])
except Exception: sys.exit(1)
vals=[]
def walk(v):
    if isinstance(v,dict):
        for k,x in v.items():
            if isinstance(x,str): vals.append(x)
            walk(x)
    elif isinstance(v,list):
        for x in v: walk(x)
    elif isinstance(v,str): vals.append(v)
walk(data)
for v in vals:
    v=re.sub(r'^https?://','',v).strip('/ ')
    if v.endswith('.up.railway.app'):
        print(v); break
else: sys.exit(1)
PY
)" || fail "Could not resolve Railway public domain"
fi
BASE_URL="https://${DOMAIN}"
log "Public URL ${BASE_URL}"

log "Waiting for first bootstrap evidence"
FIRST_BOOT=false
for _ in $(seq 1 60); do
  if BODY="$(curl -fsS --max-time 10 "$BASE_URL/health/production-acceptance" 2>/dev/null)"; then
    printf '%s\n' "$BODY" > first-boot-acceptance.json
    FIRST_BOOT=true
    break
  fi
  sleep 4
done
[ "$FIRST_BOOT" = true ] || fail "Production acceptance endpoint did not become reachable"

log "Restarting once to prove persistent state across boots"
railway restart --service "$SERVICE_NAME" --yes --json >/dev/null

# Resolve owner token only inside the authenticated runner. Never print it.
if [ -n "$OWNER_TOKEN_GENERATED" ]; then
  OWNER_TOKEN_VALUE="$OWNER_TOKEN_GENERATED"
else
  VAR_JSON="$(railway variable list --service "$SERVICE_NAME" --json)"
  export VAR_JSON
  OWNER_TOKEN_VALUE="$(python3 - <<'PY'
import json, os, sys
try: data=json.loads(os.environ['VAR_JSON'])
except Exception: sys.exit(1)
if isinstance(data,dict) and isinstance(data.get('OWNER_TOKEN'),str):
    print(data['OWNER_TOKEN']); raise SystemExit

def walk(v):
    if isinstance(v,dict):
        if v.get('name') == 'OWNER_TOKEN' and isinstance(v.get('value'),str):
            return v['value']
        for x in v.values():
            y=walk(x)
            if y: return y
    elif isinstance(v,list):
        for x in v:
            y=walk(x)
            if y: return y
    return None
x=walk(data)
if not x: sys.exit(1)
print(x)
PY
)" || fail "Unable to resolve OWNER_TOKEN for acceptance test"
fi

if [ -n "$GPT_ACTION_TOKEN_GENERATED" ]; then
  GPT_ACTION_TOKEN_VALUE="$GPT_ACTION_TOKEN_GENERATED"
else
  VAR_JSON="$(railway variable list --service "$SERVICE_NAME" --json)"
  export VAR_JSON
  GPT_ACTION_TOKEN_VALUE="$(python3 - <<'PY'
import json, os, sys
try: data=json.loads(os.environ['VAR_JSON'])
except Exception: sys.exit(1)
if isinstance(data,dict) and isinstance(data.get('GPT_ACTION_TOKEN'),str):
    print(data['GPT_ACTION_TOKEN']); raise SystemExit

def walk(v):
    if isinstance(v,dict):
        if v.get('name') == 'GPT_ACTION_TOKEN' and isinstance(v.get('value'),str):
            return v['value']
        for x in v.values():
            y=walk(x)
            if y: return y
    elif isinstance(v,list):
        for x in v:
            y=walk(x)
            if y: return y
    return None
x=walk(data)
if not x: sys.exit(1)
print(x)
PY
)" || fail "Unable to resolve GPT_ACTION_TOKEN for acceptance test"
fi

export SARA_OWNER_TOKEN="$OWNER_TOKEN_VALUE"
export SARA_GPT_ACTION_TOKEN="$GPT_ACTION_TOKEN_VALUE"
ACCEPTED=false
for _ in $(seq 1 75); do
  if python3 tools/railway_runtime_acceptance.py "$BASE_URL" --require-gpt-action-token > railway-activation-report.json 2>railway-acceptance.err; then
    ACCEPTED=true
    break
  fi
  sleep 4
done
unset SARA_OWNER_TOKEN SARA_GPT_ACTION_TOKEN OWNER_TOKEN_VALUE OWNER_TOKEN_GENERATED GPT_ACTION_TOKEN_VALUE GPT_ACTION_TOKEN_GENERATED
[ "$ACCEPTED" = true ] || {
  cat railway-acceptance.err >&2 || true
  cat railway-activation-report.json >&2 || true
  fail "Live V3.2.1 production acceptance did not pass"
}

python3 - <<PY
import json
p='railway-activation-report.json'
d=json.load(open(p,encoding='utf-8'))
d['release_version']='3.2.1'
d['project_id']='$PROJECT_ID'
d['project_name']='$PROJECT_NAME'
d['service']='$SERVICE_NAME'
d['public_url']='$BASE_URL'
d['owner_token_storage']='Railway service variable only; never printed or included in artifacts'
d['gpt_action_token_storage']='Railway service variable only; never printed or included in artifacts'
open(p,'w',encoding='utf-8').write(json.dumps(d,indent=2,sort_keys=True)+'\n')
PY

printf '%s\n' "$BASE_URL" > railway-public-url.txt
log "PRODUCTION ACCEPTANCE PASS ${BASE_URL}"
