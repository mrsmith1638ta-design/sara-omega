from datetime import datetime, timezone

class StructuredTelemetry:
    SENSITIVE={"token","password","secret","authorization","api_key","apikey","credential"}
    def _redact(self,value,key=None):
        if key and key.lower() in self.SENSITIVE: return "[REDACTED]"
        if isinstance(value,dict): return {k:self._redact(v,k) for k,v in value.items()}
        if isinstance(value,list): return [self._redact(v) for v in value]
        return value
    def event(self,name,attributes):
        if not name: raise ValueError("event name required")
        return {"name":name,"timestamp":datetime.now(timezone.utc).isoformat(),"attributes":self._redact(dict(attributes))}
