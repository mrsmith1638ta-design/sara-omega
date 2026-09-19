from dataclasses import dataclass
from datetime import datetime, timezone
import copy
@dataclass(frozen=True)
class TwinEntity:
    entity_id:str; state:dict; source:str; observed_at:str
class DigitalTwin:
    def __init__(self): self._entities={}
    def observe(self,entity_id,state,verified,source):
        if not verified: return False
        self._entities[entity_id]=TwinEntity(entity_id,copy.deepcopy(state),source,datetime.now(timezone.utc).isoformat()); return True
    def get(self,entity_id): return self._entities.get(entity_id)
    def snapshot(self): return copy.deepcopy({k:v.state for k,v in self._entities.items()})
