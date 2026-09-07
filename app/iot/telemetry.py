from __future__ import annotations
import uuid
from datetime import datetime,timezone
from .models import TelemetryEvent
class TelemetryService:
    def __init__(self,store,guard): self.store=store; self.guard=guard
    def ingest(self,envelope,supplied_secret,transport):
        if transport not in {'https','mqtt'}: raise ValueError('unsupported_iot_transport')
        self.guard.authenticate_telemetry(envelope,supplied_secret)
        e=TelemetryEvent(event_id=str(uuid.uuid4()),device_id=envelope.device_id,message_id=envelope.message_id,event_timestamp=envelope.event_timestamp,received_at=datetime.now(timezone.utc),transport=transport,topic=envelope.topic,metrics=dict(envelope.metrics)); self.store.record_telemetry(e); return e
