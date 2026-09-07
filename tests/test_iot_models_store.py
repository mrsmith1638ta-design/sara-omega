from datetime import datetime,timezone,timedelta
from app.iot.models import DeviceRecord,TelemetryEvent
from app.iot.store import IoTStore

def dev(): return DeviceRecord(device_id='galaxy-s25',name='Samsung Galaxy S25',device_class='android',model='Galaxy S25',adapter='android',capabilities={'health.read'},allowed_commands=set(),metric_allowlist={'battery_temperature_c'})
def test_persistence(tmp_path,monkeypatch):
    monkeypatch.setenv('SARA_DATA_DIR',str(tmp_path)); s=IoTStore.from_env(); s.register_device(dev(),'x'*24); s.close(); assert IoTStore.from_env().get_device('galaxy-s25')==dev()
def test_secret_is_hashed(tmp_path,monkeypatch):
    monkeypatch.setenv('SARA_DATA_DIR',str(tmp_path)); s=IoTStore.from_env(); secret='s'*32; s.register_device(dev(),secret); assert s.verify_device_secret('galaxy-s25',secret); assert not s.verify_device_secret('galaxy-s25','wrong'*8)
def test_retention(tmp_path,monkeypatch):
    monkeypatch.setenv('SARA_DATA_DIR',str(tmp_path)); monkeypatch.setenv('SARA_IOT_MAX_EVENTS_PER_DEVICE','10'); s=IoTStore.from_env(); s.register_device(dev(),'x'*24); now=datetime.now(timezone.utc)
    for i in range(11): s.record_telemetry(TelemetryEvent(event_id=f'event-{i:03d}',device_id='galaxy-s25',message_id=f'message-{i:03d}',event_timestamp=now+timedelta(seconds=i),received_at=now+timedelta(seconds=i),transport='https',topic='telemetry',metrics={'battery_temperature_c':30+i}))
    assert len(s.recent_telemetry('galaxy-s25',limit=50))==10
