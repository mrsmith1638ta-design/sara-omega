from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4
@dataclass
class Incident:
    incident_id:str; title:str; severity:str; created_at:str; timeline:list[dict]=field(default_factory=list); affected_entities:set[str]=field(default_factory=set); containment_state:str="OPEN"
class IncidentCommander:
    def __init__(self,twin): self.twin=twin; self.incidents={}
    def create(self,title,severity,affected=()):
        i=Incident(str(uuid4()),title,severity,datetime.now(timezone.utc).isoformat(),affected_entities=set(affected)); i.timeline.append({"event":"created","at":i.created_at}); self.incidents[i.incident_id]=i; return i
    def contain(self,incident_id,reason):
        i=self.incidents[incident_id]; i.containment_state="CONTAINED"; i.timeline.append({"event":"contained","reason":reason,"at":datetime.now(timezone.utc).isoformat()}); return i
    def blast_radius(self,incident_id): return tuple(sorted(self.incidents[incident_id].affected_entities))
