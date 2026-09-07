from datetime import datetime,timezone,timedelta
import pytest
from app.iot.auth import IoTIngressGuard
from app.iot.models import AuthenticationRejected,DeviceRecord,FreshnessRejected,ReplayRejected,TelemetryEnvelope
from app.iot.store import IoTStore

def fixture(tmp_path,monkeypatch):
    monkeypatch.setenv('SARA_DATA_DIR',str(tmp_path))
    monkeypatch.setenv('SARA_DEVICE_CONTROL_AUTH_TOKEN','unit-device-control')
    monkeypatch.setenv('SARA_RAILWAY_CONTROL_AUTH_TOKEN','unit-deploy-control')
    s=IoTStore.from_env()
    d=DeviceRecord(device_id='phone',name='Phone',device_class='android',model='Galaxy S25',adapter='android',allowed_commands={'health.query'},metric_allowlist={'temperature'})
    s.register_device(d,'a'*24)
    return s,IoTIngressGuard(s),d

def test_deployment_token_cannot_control(tmp_path,monkeypatch):
    s,g,d=fixture(tmp_path,monkeypatch)
    with pytest.raises(AuthenticationRejected): g.authorize_control(d,'unit-deploy-control','health.query')

def test_unregistered_device_no_trust(tmp_path,monkeypatch):
    s,g,d=fixture(tmp_path,monkeypatch)
    e=TelemetryEnvelope(device_id='stranger',message_id='message-0001',event_timestamp=datetime.now(timezone.utc),metrics={})
    with pytest.raises(AuthenticationRejected): g.authenticate_telemetry(e,'a'*24)

def test_stale_and_replay(tmp_path,monkeypatch):
    s,g,d=fixture(tmp_path,monkeypatch)
    stale=TelemetryEnvelope(device_id='phone',message_id='message-old1',event_timestamp=datetime.now(timezone.utc)-timedelta(hours=1),metrics={'temperature':20})
    with pytest.raises(FreshnessRejected): g.authenticate_telemetry(stale,'a'*24)
    e=TelemetryEnvelope(device_id='phone',message_id='message-new1',event_timestamp=datetime.now(timezone.utc),metrics={'temperature':20})
    g.authenticate_telemetry(e,'a'*24)
    with pytest.raises(ReplayRejected): g.authenticate_telemetry(e,'a'*24)
