from __future__ import annotations
import hashlib,hmac,json,os,uuid
from .adapters.base import AdapterOutcome
from .models import CapabilityUnavailable,CommandRecord,CommandStatus,DeviceCommandIntent,SubmissionUnverified
class CommandService:
    def __init__(self,store,guard,adapter_factory): self.store=store; self.guard=guard; self.adapter_factory=adapter_factory
    @staticmethod
    def _hash(device_id,action,parameters,session_id,requested_by):
        return hashlib.sha256(json.dumps({'device_id':device_id,'action':action,'parameters':parameters,'session_id':session_id,'requested_by':requested_by},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    @staticmethod
    def _verify_confirmation(supplied):
        expected=os.getenv('SARA_DEVICE_CONFIRMATION_TOKEN','').strip(); forbidden={os.getenv(x,'').strip() for x in ('OWNER_TOKEN','GPT_ACTION_TOKEN','TEST_TOKEN','SARA_DEVICE_CONTROL_AUTH_TOKEN','SARA_RAILWAY_CONTROL_AUTH_TOKEN','SARA_SOURCE_CONTROL_AUTH_TOKEN')}; forbidden.discard('')
        if not expected or expected in forbidden: raise PermissionError('device_confirmation_authority_not_separately_configured')
        if not supplied or supplied in forbidden or not hmac.compare_digest(expected,supplied): raise PermissionError('explicit_confirmation_rejected')
    def prepare(self,device_id,action,parameters,session_id,requested_by):
        d=self.store.get_device(device_id)
        if d is None or not d.enabled: raise CapabilityUnavailable('device_unavailable')
        if action not in d.allowed_commands: raise CapabilityUnavailable('command_not_in_device_allowlist')
        a=self.adapter_factory(d)
        if action not in a.supported_commands(): raise CapabilityUnavailable('adapter_capability_unavailable')
        rec=CommandRecord(command_id=str(uuid.uuid4()),device_id=device_id,action=action,parameters=dict(parameters),session_id=session_id,requested_by=requested_by,request_hash=self._hash(device_id,action,parameters,session_id,requested_by))
        return self.store.reserve_command(rec)
    def execute(self,command_id,control_token,confirmation_token=None):
        rec=self.store.get_command(command_id)
        if rec is None: raise KeyError('command_not_found')
        if rec.status==CommandStatus.SUBMISSION_UNVERIFIED: raise SubmissionUnverified('prior_submission_outcome_unverified_no_retry')
        if rec.status in {CommandStatus.COMPLETED,CommandStatus.REJECTED,CommandStatus.RESERVED}: raise ValueError(f'command_state_blocks_execution:{rec.status.value}')
        d=self.store.get_device(rec.device_id)
        if d is None: raise CapabilityUnavailable('device_unavailable')
        self.guard.authorize_control(d,control_token,rec.action)
        if rec.action in d.confirmation_required: self._verify_confirmation(confirmation_token)
        if d.adapter=='android':
            return self.store.update_command(command_id,CommandStatus.RESERVED,{'delivery':'DEVICE_POLL'})
        self.store.update_command(command_id,CommandStatus.RESERVED,None)
        intent=DeviceCommandIntent(command_id=rec.command_id,device_id=rec.device_id,action=rec.action,parameters=rec.parameters,session_id=rec.session_id,requested_by=rec.requested_by)
        result=self.adapter_factory(d).execute(intent); payload={'outcome':result.outcome.value,'detail':result.detail,'data':result.data or {}}
        if result.outcome==AdapterOutcome.ACKNOWLEDGED: return self.store.update_command(command_id,CommandStatus.COMPLETED,payload)
        if result.outcome in {AdapterOutcome.REJECTED,AdapterOutcome.CAPABILITY_UNAVAILABLE}: return self.store.update_command(command_id,CommandStatus.REJECTED,payload)
        return self.store.update_command(command_id,CommandStatus.SUBMISSION_UNVERIFIED,payload)
