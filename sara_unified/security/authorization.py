class Authorizer:
    def __init__(self, grants=None):
        self.grants = {r:set(p) for r,p in (grants or {}).items()}
    def allowed(self, roles, permission):
        return bool(roles) and any(permission in self.grants.get(role, set()) for role in roles)
