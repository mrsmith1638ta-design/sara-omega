#!/usr/bin/env bash
set -euo pipefail
apk=${1:?apk path required}
[[ -f "$apk" ]] || { echo "apk not found" >&2; exit 1; }
BUILD_TOOLS=${ANDROID_HOME:?ANDROID_HOME required}/build-tools/35.0.0
"$BUILD_TOOLS/apksigner" verify --verbose --print-certs "$apk" >/tmp/sara-apksigner.txt
"$BUILD_TOOLS/aapt" dump badging "$apk" | grep -q "package: name='com.saraomega.companion'"
if unzip -p "$apk" 2>/dev/null | strings | grep -Eiq '(sk-proj-|Bearer [A-Za-z0-9._~+/-]{20,}|SARA_DEVICE_CONTROL_AUTH_TOKEN=|BEGIN (RSA |EC |)PRIVATE KEY)'; then
  echo "credential-like material found in APK" >&2
  exit 1
fi
sha256sum "$apk"
echo "apk verification passed"
