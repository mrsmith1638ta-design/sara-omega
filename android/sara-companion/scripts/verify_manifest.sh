#!/usr/bin/env bash
set -euo pipefail
merged=$(find app/build/intermediates -path '*merged_manifest*' -name AndroidManifest.xml | head -n 1)
source_manifest=app/src/main/AndroidManifest.xml
if [[ -z "${merged:-}" || ! -f "$merged" ]]; then
  echo "merged manifest not found" >&2
  exit 1
fi
if [[ ! -f "$source_manifest" ]]; then
  echo "source manifest not found" >&2
  exit 1
fi
python - "$source_manifest" "$merged" <<'PY'
import sys
import xml.etree.ElementTree as ET

source_path, merged_path = sys.argv[1:3]
android = '{http://schemas.android.com/apk/res/android}'
allowed_direct = {
    'android.permission.INTERNET',
    'android.permission.ACCESS_NETWORK_STATE',
}

def requested_permissions(path):
    root = ET.parse(path).getroot()
    return {
        node.attrib.get(android + 'name')
        for node in root.findall('uses-permission')
        if node.attrib.get(android + 'name')
    }

source_requested = requested_permissions(source_path)
if source_requested != allowed_direct:
    raise SystemExit(
        'app source manifest permissions must be exactly '
        + repr(sorted(allowed_direct))
        + '; found '
        + repr(sorted(source_requested))
    )

root = ET.parse(merged_path).getroot()
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

# WorkManager/AndroidX may merge normal scheduling permissions needed for its
# own internal JobService/receivers. Explicitly fail on user-sensitive classes
# that this V1 design prohibits, regardless of whether a dependency adds them.
merged_requested = requested_permissions(merged_path)
forbidden_sensitive = {
    'android.permission.CAMERA',
    'android.permission.RECORD_AUDIO',
    'android.permission.ACCESS_FINE_LOCATION',
    'android.permission.ACCESS_COARSE_LOCATION',
    'android.permission.READ_CONTACTS',
    'android.permission.WRITE_CONTACTS',
    'android.permission.READ_SMS',
    'android.permission.SEND_SMS',
    'android.permission.READ_CALL_LOG',
    'android.permission.WRITE_CALL_LOG',
    'android.permission.MANAGE_EXTERNAL_STORAGE',
    'android.permission.REQUEST_INSTALL_PACKAGES',
    'android.permission.QUERY_ALL_PACKAGES',
}
bad = merged_requested & forbidden_sensitive
if bad:
    raise SystemExit('forbidden sensitive merged permission(s): ' + ','.join(sorted(bad)))

print('manifest security gate passed')
PY
