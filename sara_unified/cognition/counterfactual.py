from dataclasses import dataclass
import copy
@dataclass(frozen=True)
class CounterfactualResult:
    simulated_state: dict; changes: dict
class CounterfactualEngine:
    def simulate(self, baseline, changes):
        state=copy.deepcopy(baseline)
        for path,value in changes.items():
            parts=path.split('.'); cur=state
            for p in parts[:-1]: cur=cur.setdefault(p,{})
            cur[parts[-1]]=copy.deepcopy(value)
        return CounterfactualResult(state,copy.deepcopy(changes))
