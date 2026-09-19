from dataclasses import dataclass
from typing import Callable
@dataclass(frozen=True)
class RecoveryAction:
    name:str; requires_approval:bool; executor:Callable[[dict],dict]
@dataclass(frozen=True)
class RecoveryResult:
    action:str; executed:bool; result:dict; reason:str
class RecoveryRegistry:
    def __init__(self): self._actions={}
    def register(self,action):
        if action.name in self._actions: raise ValueError("duplicate recovery action")
        self._actions[action.name]=action
    def execute(self,name,context,approved=False):
        action=self._actions.get(name)
        if not action: return RecoveryResult(name,False,{},"action not allowlisted")
        if action.requires_approval and not approved: return RecoveryResult(name,False,{},"approval required")
        return RecoveryResult(name,True,action.executor(dict(context)),"executed")
