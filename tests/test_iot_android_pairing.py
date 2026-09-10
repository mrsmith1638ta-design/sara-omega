import pytest
from app.iot.models import CommandRecord, CommandStatus
from app.iot.pairing import PairingRejected, PairingService
from app.iot.store import IoTStore


def test_pairing_code_is_single_use(tmp_path, monkeypatch):
    monkeypatch.setenv('SARA_DATA_DIR', str(tmp_path))
    service = PairingService.for_test()
    code = service.issue(device_class='android', model_prefix='SM-')
    first = service.claim_android(
        code=code,
        name='Tommy Galaxy',
        model='SM-S938U',
        manufacturer='samsung',
        android_version='16',
        capabilities={'health.query', 'telemetry.send_now', 'factory_reset'},
        metrics={'battery_percent', 'charging', 'heartbeat', 'imaginary_metric'},
    )
    assert first.device_id.startswith('android-')
    assert len(first.device_secret) >= 32
    assert first.accepted_commands == {'health.query', 'telemetry.send_now'}
    assert first.accepted_metrics == {'battery_percent', 'charging', 'heartbeat'}
    with pytest.raises(PairingRejected, match='pairing_code_invalid_or_consumed'):
        service.claim_android(
            code=code,
            name='Second Device',
            model='SM-X920',
            manufacturer='samsung',
            android_version='16',
            capabilities={'health.query'},
            metrics={'heartbeat'},
        )


def test_pairing_model_prefix_mismatch_does_not_consume_code(tmp_path, monkeypatch):
    monkeypatch.setenv('SARA_DATA_DIR', str(tmp_path))
    service = PairingService.for_test()
    code = service.issue(model_prefix='SM-S')
    with pytest.raises(PairingRejected):
        service.claim_android(code=code, name='Bad', model='SM-X920', manufacturer='samsung', android_version='16', capabilities={'health.query'}, metrics={'heartbeat'})
    ok = service.claim_android(code=code, name='S25', model='SM-S938U', manufacturer='samsung', android_version='16', capabilities={'health.query'}, metrics={'heartbeat'})
    assert ok.accepted_commands == {'health.query'}


def test_pending_commands_are_device_bound(tmp_path, monkeypatch):
    monkeypatch.setenv('SARA_DATA_DIR', str(tmp_path))
    service = PairingService.for_test()
    code1 = service.issue(); s25 = service.claim_android(code=code1, name='S25', model='SM-S938U', manufacturer='samsung', android_version='16', capabilities={'health.query'}, metrics={'heartbeat'})
    code2 = service.issue(); tab = service.claim_android(code=code2, name='Tab S10', model='SM-X920', manufacturer='samsung', android_version='16', capabilities={'health.query'}, metrics={'heartbeat'})
    store = IoTStore.from_env()
    rec = CommandRecord(command_id='command-12345678', device_id=s25.device_id, action='health.query', parameters={}, session_id='session-1', requested_by='owner', request_hash='a'*64, status=CommandStatus.RESERVED, result={'delivery':'DEVICE_POLL'})
    store.reserve_command(rec)
    assert len(store.pending_commands_for_device(s25.device_id)) == 1
    assert store.pending_commands_for_device(tab.device_id) == []
    with pytest.raises(KeyError):
        store.acknowledge_device_command(tab.device_id, rec.command_id, CommandStatus.COMPLETED, {'ok': True})
    done = store.acknowledge_device_command(s25.device_id, rec.command_id, CommandStatus.COMPLETED, {'ok': True})
    assert done.status is CommandStatus.COMPLETED
    with pytest.raises(ValueError, match='command_not_acknowledgeable'):
        store.acknowledge_device_command(s25.device_id, rec.command_id, CommandStatus.COMPLETED, {'ok': True})
