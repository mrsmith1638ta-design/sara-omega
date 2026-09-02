#!/usr/bin/env bash
set -euo pipefail

log(){ printf '[SARA-OMEGA V3.2.1] %s\n' "$*"; }
fail(){ printf '[SARA-OMEGA V3.2.1] ERROR: %s\n' "$*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROVISION_SCRIPT="$SCRIPT_DIR/railway_account_provision.sh"

[ -f "$PROVISION_SCRIPT" ] || fail "railway_account_provision.sh was not found"

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

# Source in this shell so the compatibility function remains available to every
# Python invocation inside the canonical provisioning controller.
# shellcheck source=tools/railway_account_provision.sh
source "$PROVISION_SCRIPT"
