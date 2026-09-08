#!/usr/bin/env bash
set -euo pipefail
manifest=$(find app/build/intermediates -path '*merged_manifest*' -name AndroidManifest.xml | head -n 1)
if [[ -z "${manifest:-}" || ! -f "$manifest" ]]; then
  echo "merged manifest not found" >&2
  exit 1
fi
python - "$manifest" <<'PY'
import sys
import xml.etree.ElementTree as ET

manifest = sys.argv[1]
android = '{http://schemas.android.com/apk/res/android}'
root = ET.parse(manifest).getroot()

allowed = {
    'android.permission.INTERNET',
    'android.permission.ACCESS_NETWORK_STATE',
}
requested = {
    node.attrib.get(android + 'name')
    for node in root.findall('uses-permission')
    if node.attrib.get(android + 'name')
}
extra = requested - allowed
missing = allowed - requested
if extra:
    raise SystemExit('forbidden requested permission(s): ' + ','.join(sorted(extra)))
if missing:
    raise SystemExit('required permission(s) missing: ' + ','.join(sorted(missing)))

app = root.find('application')
if app is None:
    raise SystemExit('application node missing')
if app.attrib.get(android + 'usesCleartextTraffic') == 'true':
    raise SystemExit('cleartext traffic enabled')

exported = []
for tag in ('activity', 'activity-alias', 'service', 'receiver', 'provider'):
    for node in app.findall(tag):
        if node.attrib.get(android + 'exported') == 'true':
            exported.append((tag, node.attrib.get(android + 'name', '')))
if exported != [('activity', 'com.saraomega.companion.ui.MainActivity')]:
    raise SystemExit('unexpected exported component(s): ' + repr(exported))

print('manifest security gate passed')
PY
