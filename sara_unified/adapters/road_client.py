import json, urllib.request
from sara_unified.governance.road import RoadStatus
class RoadHTTPClient:
    def __init__(self,url,timeout=3): self.url=url; self.timeout=timeout
    def get_status(self):
        with urllib.request.urlopen(self.url,timeout=self.timeout) as r: data=json.load(r)
        return RoadStatus(True, bool(data.get("evidence_state")=="VERIFIED"), bool(data.get("production_accepted")), str(data.get("evidence_state","UNVERIFIED")))
