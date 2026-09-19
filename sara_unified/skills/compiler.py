from dataclasses import dataclass
@dataclass(frozen=True)
class WorkflowStep:
    name:str; permission:str; external_effect:bool; rollback:str|None; approval_required:bool=False
@dataclass(frozen=True)
class CompiledSkill:
    name:str; steps:tuple[WorkflowStep,...]; permissions:tuple[str,...]
class SkillCompiler:
    def compile(self,name,steps):
        steps=tuple(steps)
        if not name or not steps: raise ValueError("skill name and steps required")
        for s in steps:
            if not s.permission: raise ValueError("every step requires a permission")
            if s.external_effect and not (s.rollback or s.approval_required): raise ValueError("external effects require rollback or approval")
        return CompiledSkill(name,steps,tuple(sorted({s.permission for s in steps})))
