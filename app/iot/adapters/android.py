from __future__ import annotations
import os,re,httpx
from .base import AdapterOutcome,AdapterResult

def _eid(device_id): return re.sub(r'[^A-Z0-9]','_',device_id.upper())
class AndroidCompanionAdapter:
    def __init__(self,device_id,client=None):
        p=f'SARA_ANDROID_AGENT_{_eid(device_id)}'; self.base_url=os.getenv(p+'_URL','').strip().rstrip('/'); self.token=os.getenv(p+'_TOKEN','').strip(); self.configured=frozenset(x.strip() for x in os.getenv(p+'_COMMANDS','').split(',') if x.strip()); self.client=client or httpx.Client(timeout=8.0)
    def supported_commands(self): return self.configured if self.base_url and self.token else frozenset()
    def _verified(self):
        if not self.base_url or not self.token: return frozenset()
        try: r=self.client.get(self.base_url+'/v1/capabilities',headers={'Authorization':f'Bearer {self.token}'})
        except httpx.TransportError: return frozenset()
        if r.status_code!=200: return frozenset()
        body=r.json(); return frozenset(str(x) for x in body.get('commands',[]) if isinstance(x,str)) if isinstance(body,dict) else frozenset()
    def execute(self,intent):
        if intent.action not in self.supported_commands(): return AdapterResult(AdapterOutcome.CAPABILITY_UNAVAILABLE,'android_action_not_configured')
        if intent.action not in self._verified(): return AdapterResult(AdapterOutcome.CAPABILITY_UNAVAILABLE,'android_agent_did_not_verify_action')
        try: r=self.client.post(self.base_url+'/v1/commands',headers={'Authorization':f'Bearer {self.token}'},json={'command_id':intent.command_id,'action':intent.action,'parameters':intent.parameters})
        except (httpx.TimeoutException,httpx.TransportError): return AdapterResult(AdapterOutcome.UNCERTAIN,'android_command_transport_outcome_unknown')
        if 200<=r.status_code<300:
            body=r.json() if r.content else {}; ack=bool(body.get('acknowledged',True)) if isinstance(body,dict) else True
            return AdapterResult(AdapterOutcome.ACKNOWLEDGED if ack else AdapterOutcome.UNCERTAIN,'android_agent_response',body if isinstance(body,dict) else {})
        if r.status_code in {400,403,404,409,422}: return AdapterResult(AdapterOutcome.REJECTED,f'android_agent_rejected:{r.status_code}')
        return AdapterResult(AdapterOutcome.UNCERTAIN,f'android_agent_unexpected_status:{r.status_code}')
