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
package_name = 'com.saraomega.companion'
launcher_name = package_name + '.ui.MainActivity'
allowed_direct = {
    'android.permission.INTERNET',
    'android.permission.ACCESS_NETWORK_STATE',
}

def requested_permissions(root):
    return {
        node.attrib.get(android + 'name')
        for node in root.findall('uses-permission')
        if node.attrib.get(android + 'name')
    }

def normalize_component(name):
    if not name:
        return ''
    if name.startswith('.'):
        return package_name + name
    if '.' not in name:
        return package_name + '.' + name
    return name

def exported_components(root):
    app = root.find('application')
    if app is None:
        raise SystemExit('application node missing')
    found = []
    for tag in ('activity', 'activity-alias', 'service', 'receiver', 'provider'):
        for node in app.findall(tag):
            if node.attrib.get(android + 'exported') == 'true':
                found.append((tag, normalize_component(node.attrib.get(android + 'name', ''))))
    return found

source_root = ET.parse(source_path).getroot()
source_requested = requested_permissions(source_root)
if source_requested != allowed_direct:
    raise SystemExit(
        'app source manifest permissions must be exactly '
        + repr(sorted(allowed_direct))
        + '; found '
        + repr(sorted(source_requested))
    )
source_exported = exported_components(source_root)
if source_exported != [('activity', launcher_name)]:
    raise SystemExit('unexpected app-authored exported component(s): ' + repr(source_exported))

merged_root = ET.parse(merged_path).getroot()
merged_app = merged_root.find('application')
if merged_app is None:
    raise SystemExit('application node missing')
if merged_app.attrib.get(android + 'usesCleartextTraffic') == 'true':
    raise SystemExit('cleartext traffic enabled')

# Dependencies such as WorkManager and ProfileInstaller may contribute their
# own protected components. They are permitted, but this application may not
# add any other exported component under the SARA package namespace.
for tag, name in exported_components(merged_root):
    if name.startswith(package_name + '.') and not (tag == 'activity' and name == launcher_name):
        raise SystemExit('unexpected SARA exported component: ' + repr((tag, name)))

# WorkManager/AndroidX may merge normal scheduling permissions. Fail on the
# user-sensitive permission classes prohibited by the approved V1 design.
merged_requested = requested_permissions(merged_root)
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
