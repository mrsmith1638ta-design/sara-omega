class SecurityState:
    def __init__(self): self._write_freezes={}; self._revoked=set()
    def freeze_writes(self, scope, reason):
        if not scope or not reason: raise ValueError("scope and reason required")
        self._write_freezes[scope]=reason
    def unfreeze_writes(self, scope): self._write_freezes.pop(scope,None)
    def can_write(self, scope): return scope not in self._write_freezes
    def freeze_reason(self, scope): return self._write_freezes.get(scope)
    def revoke(self, credential_id): self._revoked.add(credential_id)
    def is_revoked(self, credential_id): return credential_id in self._revoked
