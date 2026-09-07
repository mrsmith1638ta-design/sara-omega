from datetime import datetime,timezone,timedelta
import pytest
from app.iot.auth import IoTIngressGuard,sanitize_log
from app.iot.models import AuthenticationRejected,DeviceRecord,ReplayRejected,FreshnessRejected,SchemaRejected,TelemetryEnvelope
from app.iot.store import IoTStore

def setup(tmp_path,monkeypatch):
    monkeypatch.setenv('SARA_DATA_DIR',str(tmp_path)); s=IoTStore.from_env(); d=DeviceRecord(device_id='galaxy-s25',name='S25',device_class='android',model='Galaxy S25',adapter='android',allowed_commands={'health.query'},metric_allowlist={'battery_temperature_c'}); s.register_device(d,'z'*24); return s,IoTIngressGuard(s),d
def env(): return TelemetryEnvelope(device_id='galaxy-s25',message_id='message-0001',event_timestamp=datetime.now(timezone.utc),metrics={'battery_temperature_c':35})
def test_replay(tmp_path,monkeypatch):
    s,g,d=setup(tmp_path,monkeypatch); g.authenticate_telemetry(env(),'z'*24)
    with pytest.raises(ReplayRejected): g.authenticate_telemetry(env(),'z'*24)
def test_stale(tmp_path,monkeypatch):
    s,g,d=setup(tmp_path,monkeypatch); e=env().model_copy(update={'event_timestamp':datetime.now(timezone.utc)-timedelta(hours=1)})
    with pytest.raises(FreshnessRejected): g.authenticate_telemetry(e,'z'*24)
def test_unknown_metric(tmp_path,monkeypatch):
    s,g,d=setup(tmp_path,monkeypatch); e=env().model_copy(update={'metrics':{'imei':'x'}})
    with pytest.raises(SchemaRejected): g.authenticate_telemetry(e,'z'*24)
def test_generic_token_cannot_control(tmp_path,monkeypatch):
    s,g,d=setup(tmp_path,monkeypatch); monkeypatch.setenv('GPT_ACTION_TOKEN','generic'); monkeypatch.setenv('SARA_DEVICE_CONTROL_AUTH_TOKEN','device-control')
    with pytest.raises(AuthenticationRejected): g.authorize_control(d,'generic','health.query')
def test_log_sanitizes():
    out=sanitize_log('bad\nline',{'token':'secret-value','name':'x\ny'}); assert 'secret-value' not in out and '\\n' not in out
