from dataclasses import dataclass
from enum import Enum
from typing import Protocol
from ..models import DeviceCommandIntent
class AdapterOutcome(str,Enum): ACKNOWLEDGED='ACKNOWLEDGED'; REJECTED='REJECTED'; CAPABILITY_UNAVAILABLE='CAPABILITY_UNAVAILABLE'; UNCERTAIN='UNCERTAIN'
@dataclass(frozen=True)
class AdapterResult: outcome:AdapterOutcome; detail:str; data:dict|None=None
class DeviceAdapter(Protocol):
    def supported_commands(self)->frozenset[str]: ...
    def execute(self,intent:DeviceCommandIntent)->AdapterResult: ...
