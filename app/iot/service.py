from __future__ import annotations
import os
from .adapters.android import AndroidCompanionAdapter
from .adapters.sony_ht_st5000 import SonyHTST5000Adapter
from .auth import IoTIngressGuard
from .commands import CommandService
from .health import DeviceHealthEngine,truth_check_device_claim
from .store import IoTStore
from .telemetry import TelemetryService
class IoTService:
    def __init__(self,store=None):
        self.store=store or IoTStore.from_env(); self.guard=IoTIngressGuard(self.store); self.telemetry=TelemetryService(self.store,self.guard); self.health_engine=DeviceHealthEngine(self.store); self.commands=CommandService(self.store,self.guard,self._adapter_for)
    @staticmethod
    def _adapter_for(device):
        if device.adapter=='android': return AndroidCompanionAdapter(device.device_id)
        if device.adapter=='sony_ht_st5000': return SonyHTST5000Adapter()
        raise ValueError('unsupported_device_adapter')
    def health(self):
        ds=self.store.list_devices(); token=os.getenv('SARA_DEVICE_CONTROL_AUTH_TOKEN','').strip()
        return {'status':'ok','module':'sara-iot-user-plane','present':True,'store_ready':self.store.db_path.exists(),'registered_devices':len(ds),'telemetry_configured':any(d.enabled and bool(d.metric_allowlist) for d in ds),'control_configured':bool(token) and any(d.enabled and bool(d.allowed_commands) for d in ds),'configured':self.store.db_path.exists(),'execution_authority':False}
    def register_device(self,record,telemetry_secret): return self.store.register_device(record,telemetry_secret)
    def ingest_telemetry(self,envelope,supplied_secret,transport): return self.telemetry.ingest(envelope,supplied_secret,transport)
    def device_health(self,device_id): return self.health_engine.evaluate(device_id)
    def prepare_command(self,device_id,action,parameters,session_id,requested_by): return self.commands.prepare(device_id,action,parameters,session_id,requested_by)
    def execute_command(self,command_id,token,confirmation_token=None): return self.commands.execute(command_id,token,confirmation_token)
    def get_command(self,command_id): return self.store.get_command(command_id)
    def context_for_problem(self,query,context):
        explicit=str(context.get('iot_device_id','')).strip(); d=self.store.get_device(explicit) if explicit else None
        if d is None:
            low=query.lower()
            for c in self.store.list_devices():
                if c.device_id.lower() in low or c.name.lower() in low or c.model.lower() in low: d=c; break
        if d is None: return None
        h=self.device_health(d.device_id); recent=self.store.recent_telemetry(d.device_id,limit=20)
        return {'device':d.model_dump(mode='json'),'health':h.model_dump(mode='json'),'observations':[{'event_id':e.event_id,'message_id':e.message_id,'event_timestamp':e.event_timestamp.isoformat(),'received_at':e.received_at.isoformat(),'metrics':e.metrics,'evidence_class':e.evidence_class.value} for e in recent],'truth_rule':'sensor observations may support an inference but do not independently verify a physical root cause','execution_authority':False}
    @staticmethod
    def truth_check(candidate,health_payload):
        from .models import DeviceHealth
        return truth_check_device_claim(candidate,DeviceHealth.model_validate(health_payload))
