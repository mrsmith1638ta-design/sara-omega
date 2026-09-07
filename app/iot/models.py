from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator

class IoTError(RuntimeError): pass
class AuthenticationRejected(IoTError): pass
class ReplayRejected(IoTError): pass
class FreshnessRejected(IoTError): pass
class RateLimitRejected(IoTError): pass
class QuarantineRejected(IoTError): pass
class SchemaRejected(IoTError): pass
class CapabilityUnavailable(IoTError): pass
class SubmissionUnverified(IoTError): pass

class CommandStatus(str, Enum):
    PREPARED='PREPARED'; RESERVED='RESERVED'; COMPLETED='COMPLETED'; REJECTED='REJECTED'; SUBMISSION_UNVERIFIED='SUBMISSION_UNVERIFIED'
class EvidenceClass(str, Enum):
    OBSERVED='OBSERVED'; SUPPORTED='SUPPORTED'; UNVERIFIED='UNVERIFIED'

class DeviceRecord(BaseModel):
    device_id: str = Field(min_length=1,max_length=128,pattern=r'^[A-Za-z0-9._-]+$')
    name: str = Field(min_length=1,max_length=160)
    device_class: str = Field(min_length=1,max_length=64)
    model: str = Field(min_length=1,max_length=128)
    adapter: str = Field(min_length=1,max_length=64)
    capabilities: set[str] = Field(default_factory=set,max_length=64)
    allowed_commands: set[str] = Field(default_factory=set,max_length=64)
    allowed_topics: set[str] = Field(default_factory=lambda:{'telemetry'},max_length=32)
    metric_allowlist: set[str] = Field(default_factory=set,max_length=128)
    enabled: bool = True
    confirmation_required: set[str] = Field(default_factory=set,max_length=32)
    trust_state: str = Field(default='REGISTERED',max_length=32)
    @field_validator('capabilities','allowed_commands','allowed_topics','metric_allowlist','confirmation_required')
    @classmethod
    def bounded_members(cls, values:set[str])->set[str]:
        if any((not v or len(v)>96) for v in values): raise ValueError('invalid_allowlist_member')
        return values

class DeviceRegistrationRequest(BaseModel):
    device: DeviceRecord
    telemetry_secret: str = Field(min_length=24,max_length=512)

class TelemetryEnvelope(BaseModel):
    device_id: str = Field(min_length=1,max_length=128)
    message_id: str = Field(min_length=8,max_length=160)
    event_timestamp: datetime
    schema_version: str = Field(default='1',min_length=1,max_length=16)
    topic: str = Field(default='telemetry',min_length=1,max_length=96)
    metrics: dict[str,int|float|bool|str] = Field(default_factory=dict,max_length=128)
    @field_validator('event_timestamp')
    @classmethod
    def aware(cls,v:datetime)->datetime:
        if v.tzinfo is None: raise ValueError('timezone_required')
        return v.astimezone(timezone.utc)

class TelemetryEvent(BaseModel):
    event_id: str; device_id: str; message_id: str; event_timestamp: datetime; received_at: datetime
    transport: str = Field(pattern=r'^(https|mqtt)$'); topic: str
    metrics: dict[str,int|float|bool|str] = Field(default_factory=dict,max_length=128)
    evidence_class: EvidenceClass = EvidenceClass.OBSERVED

class DeviceHealth(BaseModel):
    device_id: str; classification: EvidenceClass
    observations: dict[str,Any]=Field(default_factory=dict); evidence_metrics:list[str]=Field(default_factory=list)
    anomalies:list[dict[str,Any]]=Field(default_factory=list); root_cause_verified: bool=False
    evaluated_at: datetime=Field(default_factory=lambda: datetime.now(timezone.utc))

class DeviceCommandIntent(BaseModel):
    command_id:str; device_id:str; action:str=Field(min_length=1,max_length=96); parameters:dict[str,Any]=Field(default_factory=dict,max_length=32)
    session_id:str=Field(min_length=1,max_length=160); requested_by:str=Field(min_length=1,max_length=128)

class CommandRecord(BaseModel):
    command_id:str; device_id:str; action:str; parameters:dict[str,Any]=Field(default_factory=dict); session_id:str; requested_by:str; request_hash:str
    status:CommandStatus=CommandStatus.PREPARED; created_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc)); updated_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc)); result:dict[str,Any]|None=None
