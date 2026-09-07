from app.iot.adapters.sony_ht_st5000 import SonyHTST5000Adapter
from app.iot.models import DeviceCommandIntent

def test_sony_write_fails_closed(monkeypatch):
    monkeypatch.delenv('SARA_SONY_HT_ST5000_STATE_URL',raising=False); a=SonyHTST5000Adapter(); assert a.supported_commands()==frozenset(); r=a.execute(DeviceCommandIntent(command_id='12345678',device_id='sony',action='volume.set',parameters={'level':20},session_id='s',requested_by='owner')); assert r.outcome.value=='CAPABILITY_UNAVAILABLE'
