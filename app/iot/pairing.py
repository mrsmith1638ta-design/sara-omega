from __future__ import annotations

import base64
import secrets
from datetime import datetime, timedelta, timezone

from .models import DeviceRecord, PairingClaimResponse
from .store import IoTStore

ANDROID_COMMANDS = frozenset({
    'health.query', 'battery.query', 'storage.query', 'network.query',
    'heartbeat.now', 'telemetry.send_now',
})
ANDROID_METRICS = frozenset({
    'battery_percent', 'charging', 'charging_source', 'battery_temperature_c',
    'storage_free_bytes', 'storage_total_bytes', 'memory_avail_bytes',
    'network_connected', 'network_type', 'uptime_seconds', 'heartbeat',
    'android_version', 'manufacturer', 'model', 'app_version',
})


class PairingRejected(RuntimeError):
    pass


class PairingService:
    def __init__(self, store: IoTStore):
        self.store = store

    @classmethod
    def from_env(cls) -> 'PairingService':
        return cls(IoTStore.from_env())

    @classmethod
    def for_test(cls) -> 'PairingService':
        return cls(IoTStore.from_env())

    def issue(self, device_class: str = 'android', model_prefix: str | None = None, ttl_seconds: int = 600) -> str:
        if device_class != 'android':
            raise PairingRejected('unsupported_device_class')
        ttl = max(60, min(int(ttl_seconds), 1800))
        raw = secrets.token_bytes(16)
        code = base64.b32encode(raw).decode('ascii').rstrip('=')
        display = '-'.join(code[i:i + 4] for i in range(0, len(code), 4))
        self.store.create_pairing_code(
            display,
            device_class,
            model_prefix,
            datetime.now(timezone.utc) + timedelta(seconds=ttl),
        )
        return display

    def claim_android(
        self,
        *,
        code: str,
        name: str,
        model: str,
        manufacturer: str,
        android_version: str,
        capabilities: set[str],
        metrics: set[str],
    ) -> PairingClaimResponse:
        claim = self.store.consume_pairing_code(code, model)
        if claim is None:
            raise PairingRejected('pairing_code_invalid_or_consumed')
        accepted_commands = set(capabilities) & set(ANDROID_COMMANDS)
        accepted_metrics = set(metrics) & set(ANDROID_METRICS)
        device_id = 'android-' + secrets.token_hex(12)
        device_secret = secrets.token_urlsafe(32)
        record = DeviceRecord(
            device_id=device_id,
            name=name,
            device_class='android',
            model=model,
            adapter='android',
            capabilities=accepted_commands,
            allowed_commands=accepted_commands,
            allowed_topics={'telemetry'},
            metric_allowlist=accepted_metrics,
            enabled=True,
            confirmation_required=set(),
            trust_state='REGISTERED',
        )
        self.store.register_device(record, device_secret)
        return PairingClaimResponse(
            device_id=device_id,
            device_secret=device_secret,
            server_base_url='https://sara-omega-production.up.railway.app/',
            accepted_commands=accepted_commands,
            accepted_metrics=accepted_metrics,
        )
