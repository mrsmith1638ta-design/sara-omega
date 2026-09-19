import copy
class MemoryStorage:
    def __init__(self): self._data={}
    def put(self,namespace,key,value):
        if not namespace or not key: raise ValueError("namespace and key required")
        self._data[(namespace,key)]=copy.deepcopy(value)
    def get(self,namespace,key): return copy.deepcopy(self._data.get((namespace,key)))
    def delete(self,namespace,key): return self._data.pop((namespace,key),None) is not None
