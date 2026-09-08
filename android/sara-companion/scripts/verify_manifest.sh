#!/usr/bin/env bash
set -euo pipefail
manifest=$(find app/build/intermediates -path '*merged_manifest*' -name AndroidManifest.xml | head -n 1)
if [[ -z "${manifest:-}" || ! -f "$manifest" ]]; then
  echo "merged manifest not found" >&2
  exit 1
fi
allowed='android.permission.INTERNET|android.permission.ACCESS_NETWORK_STATE'
perms=$(grep -o 'android.permission.[A-Z0-9_]*' "$manifest" | sort -u || true)
while read -r p; do
  [[ -z "$p" ]] && continue
  if ! grep -Eq "^(${allowed})$" <<<"$p"; then
    echo "forbidden permission: $p" >&2
    exit 1
  fi
done <<<"$perms"
if grep -q 'usesCleartextTraffic="true"' "$manifest"; then
  echo "cleartext traffic enabled" >&2
  exit 1
fi
count=$(grep -c 'android:exported="true"' "$manifest" || true)
if [[ "$count" -gt 1 ]]; then
  echo "unexpected exported component" >&2
  exit 1
fi
echo "manifest security gate passed"
