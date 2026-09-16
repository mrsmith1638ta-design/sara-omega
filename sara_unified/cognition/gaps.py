from dataclasses import dataclass
@dataclass(frozen=True)
class KnowledgeGap:
    category:str; severity:str; subject:str; evidence:str; human_approval_required:bool
class KnowledgeGapRadar:
    def derive(self, claims=(), dependencies=(), tested_capabilities=()):
        gaps=[]
        for c in claims:
            if getattr(c.status,'value',c.status) in {"DISPUTED","UNVERIFIED","UNKNOWN","CURRENTLY_INACCESSIBLE"}: gaps.append(KnowledgeGap("evidence","HIGH",c.statement,c.claim_id,False))
        tested=set(tested_capabilities)
        for d in dependencies:
            if not d.get("documented",False): gaps.append(KnowledgeGap("dependency","MEDIUM",d["name"],"undocumented",True))
            if d.get("capability") and d["capability"] not in tested: gaps.append(KnowledgeGap("test","MEDIUM",d["capability"],"missing test evidence",False))
        return gaps
