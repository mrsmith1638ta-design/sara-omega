import pytest
from app.iot.adapters.base import AdapterOutcome,AdapterResult
from app.iot.auth import IoTIngressGuard
from app.iot.commands import CommandService
from app.iot.models import CapabilityUnavailable,DeviceRecord,SubmissionUnverified
from app.iot.store import IoTStore
class Uncertain:
    calls=0
    def supported_commands(self): return frozenset({'health.query'})
    def execute(self,intent): self.calls+=1; return AdapterResult(AdapterOutcome.UNCERTAIN,'unknown')
class Factory:
    def __init__(self,a): self.a=a
    def __call__(self,d): return self.a

def setup(tmp_path,monkeypatch,confirmation=False):
    monkeypatch.setenv('SARA_DATA_DIR',str(tmp_path)); monkeypatch.setenv('SARA_DEVICE_CONTROL_AUTH_TOKEN','device-control'); s=IoTStore.from_env(); d=DeviceRecord(device_id='galaxy-s25',name='S25',device_class='test',model='Galaxy S25',adapter='test_uncertain',allowed_commands={'health.query'},confirmation_required={'health.query'} if confirmation else set()); s.register_device(d,'x'*24); a=Uncertain(); return CommandService(s,IoTIngressGuard(s),Factory(a)),a

def test_unknown_command_rejected(tmp_path,monkeypatch):
    cs,a=setup(tmp_path,monkeypatch)
    with pytest.raises(CapabilityUnavailable): cs.prepare('galaxy-s25','factory_reset',{},'session-1','owner')
def test_uncertain_not_retried(tmp_path,monkeypatch):
    cs,a=setup(tmp_path,monkeypatch); c=cs.prepare('galaxy-s25','health.query',{},'session-1','owner'); r=cs.execute(c.command_id,'device-control'); assert r.status.value=='SUBMISSION_UNVERIFIED'
    with pytest.raises(SubmissionUnverified): cs.execute(c.command_id,'device-control')
    assert a.calls==1
def test_confirmation_must_use_separate_verified_authority(tmp_path,monkeypatch):
    cs,a=setup(tmp_path,monkeypatch,confirmation=True); c=cs.prepare('galaxy-s25','health.query',{},'session-1','owner')
    monkeypatch.setenv('SARA_DEVICE_CONFIRMATION_TOKEN','confirmation-only')
    with pytest.raises(PermissionError): cs.execute(c.command_id,'device-control','device-control')
    assert a.calls==0
