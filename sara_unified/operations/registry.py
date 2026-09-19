from dataclasses import dataclass
@dataclass(frozen=True)
class ServiceRegistration:
    service_id:str; version:str; dependencies:tuple[str,...]; permissions:tuple[str,...]
class ServiceRegistry:
    def __init__(self): self._items={}
    def register(self,item):
        if item.service_id in self._items and self._items[item.service_id].version != item.version: raise ValueError("service already registered at another version")
        self._items[item.service_id]=item
    def get(self,service_id): return self._items.get(service_id)
    def all(self): return tuple(self._items.values())
