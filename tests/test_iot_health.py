from datetime import datetime,timezone,timedelta
from app.iot.health import DeviceHealthEngine,truth_check_device_claim
from app.iot.models import DeviceRecord,TelemetryEvent
from app.iot.store import IoTStore

def test_drift_supported_not_verified(tmp_path,monkeypatch):
    monkeypatch.setenv('SARA_DATA_DIR',str(tmp_path)); s=IoTStore.from_env(); d=DeviceRecord(device_id='galaxy-s25',name='S25',device_class='android',model='Galaxy S25',adapter='android',metric_allowlist={'battery_temperature_c'}); s.register_device(d,'x'*24); now=datetime.now(timezone.utc)
    for i,v in enumerate([30,31,42]): s.record_telemetry(TelemetryEvent(event_id=f'event-{i:03d}',device_id=d.device_id,message_id=f'message-{i:03d}',event_timestamp=now+timedelta(seconds=i),received_at=now+timedelta(seconds=i),transport='https',topic='telemetry',metrics={'battery_temperature_c':v}))
    h=DeviceHealthEngine(s).evaluate(d.device_id); assert h.classification.value=='SUPPORTED' and not h.root_cause_verified; gate=truth_check_device_claim('The battery has failed.',h); assert gate['fail_closed'] and not gate['allowed']
def test_missing_metric_not_invented(tmp_path,monkeypatch):
    monkeypatch.setenv('SARA_DATA_DIR',str(tmp_path)); s=IoTStore.from_env(); d=DeviceRecord(device_id='sony-ht-st5000',name='Sony',device_class='audio',model='HT-ST5000',adapter='sony_ht_st5000',metric_allowlist={'reachable'}); s.register_device(d,'x'*24); h=DeviceHealthEngine(s).evaluate(d.device_id); assert 'battery_temperature_c' not in h.observations
