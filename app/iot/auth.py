from __future__ import annotations
import hmac,json,os,re
from datetime import datetime,timedelta,timezone
from typing import Any
from .models import AuthenticationRejected,FreshnessRejected,QuarantineRejected,RateLimitRejected,ReplayRejected,SchemaRejected,TelemetryEnvelope
from .store import IoTStore

def sanitize_log(event:str,fields:dict[str,Any]|None=None)->str:
    def clean(v,key=''):
        if re.search(r'(?i)(secret|token|authorization|credential|password|key)',key): return '[REDACTED]'
        if isinstance(v,dict): return {str(k)[:64]:clean(x,str(k)) for k,x in list(v.items())[:32]}
        if isinstance(v,str): return re.sub(r'[\x00-\x1f\x7f]+','_',v)[:256]
        return v
    return json.dumps({'event':clean(event),'fields':clean(fields or {})},sort_keys=True,separators=(',',':'))[:1024]

class IoTIngressGuard:
    def __init__(self,store:IoTStore):
        self.store=store; self.freshness_seconds=max(10,min(int(os.getenv('SARA_IOT_FRESHNESS_SECONDS','120')),3600)); self.max_payload_bytes=max(1024,min(int(os.getenv('SARA_IOT_MAX_PAYLOAD_BYTES','32768')),1048576)); self.rate_limit=max(1,min(int(os.getenv('SARA_IOT_EVENTS_PER_MINUTE','120')),6000)); self.failure_threshold=max(2,min(int(os.getenv('SARA_IOT_FAILURE_THRESHOLD','5')),100)); self.quarantine_seconds=max(60,min(int(os.getenv('SARA_IOT_QUARANTINE_SECONDS','900')),86400))
    def _failure(self,device_id,kind):
        now=datetime.now(timezone.utc); cutoff=(now-timedelta(minutes=10)).isoformat(); self.store.record_failure(device_id,kind)
        if self.store.failure_count(device_id,cutoff)>=self.failure_threshold: self.store.record_failure(device_id,'quarantined',(now+timedelta(seconds=self.quarantine_seconds)).isoformat())
    def authenticate_telemetry(self,envelope:TelemetryEnvelope,supplied_secret:str):
        d=self.store.get_device(envelope.device_id)
        if d is None or not d.enabled: self._failure(envelope.device_id,'unknown_or_disabled'); raise AuthenticationRejected('device_not_registered_or_disabled')
        until=self.store.quarantine_until(d.device_id); now=datetime.now(timezone.utc)
        if until and until>now: raise QuarantineRejected('device_quarantined')
        if not self.store.verify_device_secret(d.device_id,supplied_secret): self._failure(d.device_id,'authentication'); raise AuthenticationRejected('device_authentication_rejected')
        delta=(now-envelope.event_timestamp).total_seconds()
        if delta < -30 or delta > self.freshness_seconds: self._failure(d.device_id,'freshness'); raise FreshnessRejected('telemetry_outside_freshness_window')
        if envelope.topic not in d.allowed_topics: self._failure(d.device_id,'topic'); raise SchemaRejected('telemetry_topic_not_allowed')
        if set(envelope.metrics)-set(d.metric_allowlist): self._failure(d.device_id,'schema'); raise SchemaRejected('telemetry_metric_not_allowed')
        if len(envelope.model_dump_json().encode())>self.max_payload_bytes: self._failure(d.device_id,'oversized'); raise SchemaRejected('telemetry_payload_too_large')
        cutoff=(now-timedelta(minutes=1)).isoformat()
        if self.store.recent_replay_count(d.device_id,cutoff)>=self.rate_limit: self._failure(d.device_id,'rate'); raise RateLimitRejected('device_rate_limit_exceeded')
        if not self.store.reserve_replay(d.device_id,envelope.message_id,now.isoformat()): self._failure(d.device_id,'replay'); raise ReplayRejected('telemetry_replay_rejected')
        return d
    def authorize_control(self,device,supplied_token,action):
        expected=os.getenv('SARA_DEVICE_CONTROL_AUTH_TOKEN','').strip(); forbidden={os.getenv(x,'').strip() for x in ('OWNER_TOKEN','GPT_ACTION_TOKEN','TEST_TOKEN','SARA_RAILWAY_CONTROL_AUTH_TOKEN','SARA_SOURCE_CONTROL_AUTH_TOKEN')}; forbidden.discard('')
        if not expected or expected in forbidden: raise AuthenticationRejected('device_control_authority_not_separately_configured')
        if not supplied_token or supplied_token in forbidden or not hmac.compare_digest(expected,supplied_token): raise AuthenticationRejected('device_control_authentication_rejected')
        if action not in device.allowed_commands: raise AuthenticationRejected('device_action_not_authorized')
