from __future__ import annotations

from .base import AdapterOutcome, AdapterResult

ANDROID_POLL_COMMANDS = frozenset({
    'health.query',
    'battery.query',
    'storage.query',
    'network.query',
    'heartbeat.now',
    'telemetry.send_now',
})


class AndroidCompanionAdapter:
    """Capability declaration for Android outbound command polling.

    The server never opens an inbound connection to the phone. Delivery is
    handled by the durable command queue and authenticated device polling.
    """

    def __init__(self, device_id: str, client=None):
        self.device_id = device_id

    def supported_commands(self) -> frozenset[str]:
        return ANDROID_POLL_COMMANDS

    def execute(self, intent):
        if intent.action not in ANDROID_POLL_COMMANDS:
            return AdapterResult(AdapterOutcome.CAPABILITY_UNAVAILABLE, 'android_action_not_allowlisted')
        return AdapterResult(AdapterOutcome.UNCERTAIN, 'android_commands_are_delivered_by_device_poll')
