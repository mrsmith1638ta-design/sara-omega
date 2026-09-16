from dataclasses import dataclass
@dataclass(frozen=True)
class DependencyHealth:
    reachable:bool; trusted:bool; mandatory:bool
class HealthAggregator:
    def __init__(self): self.dependencies={}; self.audit_chain_valid=True; self.evidence_store_writable=True
    def set_dependency(self,name,reachable,trusted,mandatory): self.dependencies[name]=DependencyHealth(reachable,trusted,mandatory)
    def ready(self): return self.audit_chain_valid and self.evidence_store_writable and all((not d.mandatory) or (d.reachable and d.trusted) for d in self.dependencies.values())
    def status(self): return {"ready":self.ready(),"dependencies":{k:d.__dict__ for k,d in self.dependencies.items()},"audit_chain_valid":self.audit_chain_valid,"evidence_store_writable":self.evidence_store_writable}
