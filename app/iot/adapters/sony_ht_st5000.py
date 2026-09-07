from __future__ import annotations
import os,httpx
from .base import AdapterOutcome,AdapterResult
class SonyHTST5000Adapter:
    def __init__(self,client=None): self.state_url=os.getenv('SARA_SONY_HT_ST5000_STATE_URL','').strip(); self.client=client or httpx.Client(timeout=5.0)
    def supported_commands(self): return frozenset({'state.read'}) if self.state_url else frozenset()
    def execute(self,intent):
        if intent.action!='state.read' or not self.state_url: return AdapterResult(AdapterOutcome.CAPABILITY_UNAVAILABLE,'sony_ht_st5000_write_interface_not_verified')
        try: r=self.client.get(self.state_url)
        except httpx.TransportError: return AdapterResult(AdapterOutcome.UNCERTAIN,'sony_state_transport_outcome_unknown')
        if r.status_code==200:
            data=r.json() if 'json' in r.headers.get('content-type','') else {'reachable':True,'status_code':200}; return AdapterResult(AdapterOutcome.ACKNOWLEDGED,'sony_state_read',data if isinstance(data,dict) else {'reachable':True})
        if r.status_code in {401,403,404}: return AdapterResult(AdapterOutcome.REJECTED,f'sony_state_rejected:{r.status_code}')
        return AdapterResult(AdapterOutcome.UNCERTAIN,f'sony_state_unexpected_status:{r.status_code}')
