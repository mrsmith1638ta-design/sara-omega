import importlib
from fastapi import FastAPI
from fastapi.testclient import TestClient

def make_client(tmp_path,monkeypatch):
    monkeypatch.setenv('SARA_DATA_DIR',str(tmp_path))
    monkeypatch.setenv('OWNER_TOKEN','unit-owner-value')
    monkeypatch.setenv('GPT_ACTION_TOKEN','unit-gpt-value')
    monkeypatch.setenv('SARA_DEVICE_CONTROL_AUTH_TOKEN','unit-device-value')
    import app.iot.router as r
    importlib.reload(r)
    app=FastAPI(); app.include_router(r.router)
    return TestClient(app)

def test_health(tmp_path,monkeypatch):
    c=make_client(tmp_path,monkeypatch); b=c.get('/iot/health').json()
    assert b['module']=='sara-iot-user-plane' and b['present'] is True

def test_generic_gpt_cannot_register(tmp_path,monkeypatch):
    c=make_client(tmp_path,monkeypatch)
    body={'device':{'device_id':'x','name':'x','device_class':'android','model':'x','adapter':'android','capabilities':[],'allowed_commands':[],'metric_allowlist':[]},'telemetry_secret':'x'*24}
    r=c.post('/iot/devices/register',headers={'Authorization':'Bearer unit-gpt-value'},json=body)
    assert r.status_code==403

def test_register_and_ingest_real_envelope(tmp_path,monkeypatch):
    from datetime import datetime,timezone
    c=make_client(tmp_path,monkeypatch); secret='s'*24
    body={'device':{'device_id':'galaxy-s25','name':'Samsung Galaxy S25','device_class':'android','model':'Galaxy S25','adapter':'android','capabilities':['health.read'],'allowed_commands':[],'metric_allowlist':['battery_temperature_c']},'telemetry_secret':secret}
    assert c.post('/iot/devices/register',headers={'Authorization':'Bearer unit-device-value'},json=body).status_code==200
    ev={'device_id':'galaxy-s25','message_id':'message-0001','event_timestamp':datetime.now(timezone.utc).isoformat(),'schema_version':'1','topic':'telemetry','metrics':{'battery_temperature_c':35.0}}
    assert c.post('/iot/telemetry',headers={'X-SARA-Device-Secret':secret},json=ev).status_code==200
    h=c.get('/iot/devices/galaxy-s25/health',headers={'Authorization':'Bearer unit-owner-value'})
    assert h.status_code==200 and h.json()['root_cause_verified'] is False
