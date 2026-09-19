class SkillRegistry:
    def __init__(self): self._skills={}; self._active=set()
    def register(self,skill): self._skills[skill.name]=skill
    def activate(self,name,policy_authorized):
        if name not in self._skills or not policy_authorized: return False
        self._active.add(name); return True
    def is_active(self,name): return name in self._active
