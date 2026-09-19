from dataclasses import dataclass
@dataclass(frozen=True)
class ExperimentPlan:
    hypothesis:str; variables:tuple[str,...]; controls:tuple[str,...]; stopping_rule:str; provenance_required:bool=True
class ExperimentCompiler:
    def compile(self,hypothesis,variables,controls,stopping_rule):
        if not hypothesis or not variables or not stopping_rule: raise ValueError("hypothesis, variables and stopping rule are required")
        return ExperimentPlan(hypothesis,tuple(variables),tuple(controls),stopping_rule)
