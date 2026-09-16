from pathlib import Path
import os
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from sara_unified.evidence.audit import AuditLedger
from sara_unified.operations.digital_twin import DigitalTwin
from sara_unified.operations.observability import HealthAggregator
from sara_unified.operations.recovery import RecoveryRegistry, RecoveryAction
from sara_unified.operations.registry import ServiceRegistry
from sara_unified.operations.incidents import IncidentCommander
from sara_unified.cognition.counterfactual import CounterfactualEngine
from sara_unified.cognition.jury import ModelJury
from sara_unified.cognition.gaps import KnowledgeGapRadar
from sara_unified.evidence.fusion import EvidenceFusion
from sara_unified.skills.registry import SkillRegistry
from sara_unified.security.authorization import Authorizer
from sara_unified.cognition.jury import JuryOpinion
from sara_unified.evidence.passports import CapabilityPassport
from sara_unified.evidence.signing import Ed25519Signer
from sara_unified.api.schemas import RecoveryRequest, CounterfactualRequest, JuryRequest, IncidentRequest, TwinObservationRequest
from sara_unified.config import Settings

class SARAUnified:
    def __init__(self,audit,authorizer=None,settings=None,allow_local_operator=True):
        self.settings=settings or Settings()
        self.allow_local_operator=allow_local_operator
        self.audit=audit; self.authorizer=authorizer or Authorizer({"operator":{"recovery:execute","twin:read","counterfactual:run"}})
        self.twin=DigitalTwin(); self.health=HealthAggregator(); self.recovery=RecoveryRegistry(); self.services=ServiceRegistry(); self.incidents=IncidentCommander(self.twin)
        self.counterfactual=CounterfactualEngine(); self.jury=ModelJury(); self.gaps=KnowledgeGapRadar(); self.fusion=EvidenceFusion(); self.skills=SkillRegistry(); self.signer=Ed25519Signer.generate()
        self.recovery.register(RecoveryAction("restart",True,lambda ctx:{"accepted":True,"service":ctx.get("service")}))
        self.api=self._build_api()
    @classmethod
    def local(cls,audit_path="./sara-audit.jsonl"): return cls(AuditLedger(Path(audit_path)))
    def _roles_from_header(self,authorization):
        if not authorization or not authorization.startswith("Bearer "): return set()
        token=authorization[7:].strip()
        return {"operator"} if self.allow_local_operator and token=="local-operator" else set()
    def _build_api(self):
        api=FastAPI(title="SARA Unified Ecosystem",version="3.2.1+unified")
        @api.middleware("http")
        async def enforce_request_size(request, call_next):
            content_length=request.headers.get("content-length")
            if content_length is not None and int(content_length) > self.settings.max_request_bytes:
                return JSONResponse(status_code=413,content={"detail":"request body too large"})
            return await call_next(request)
        @api.get("/health")
        def health(): return {"alive":True,"audit_chain_valid":self.audit.verify(),"version":"3.2.1+unified"}
        @api.get("/readyz")
        def ready():
            self.health.audit_chain_valid=self.audit.verify(); status=self.health.status()
            return JSONResponse(status_code=200 if status["ready"] else 503,content=status)
        @api.get("/v1/capabilities")
        def capabilities(): return {"capabilities":["evidence-fusion","digital-twin","model-jury","counterfactual","gap-radar","governed-recovery","incident-command","skill-registry"]}
        @api.get("/v1/twin")
        def twin_snapshot(): return {"entities": self.twin.snapshot()}
        @api.post("/v1/twin/observe")
        def twin_observe(req:TwinObservationRequest,authorization:str|None=Header(default=None)):
            roles=self._roles_from_header(authorization)
            if not self.authorizer.allowed(roles,"recovery:execute"): raise HTTPException(status_code=401,detail="unauthorized")
            if not req.verified: raise HTTPException(status_code=422,detail="unverified observations cannot mutate canonical twin")
            self.twin.observe(req.entity_id,req.state,True,req.source)
            self.audit.append("api","TWIN_OBSERVED",{"entity_id":req.entity_id,"source":req.source})
            return {"accepted":True,"entity_id":req.entity_id}
        @api.get("/v1/evidence/audit-status")
        def audit_status(): return {"valid": self.audit.verify()}
        @api.get("/v1/passports/{capability_id}")
        def passport(capability_id:str):
            allowed={"evidence-fusion","digital-twin","model-jury","counterfactual","gap-radar","governed-recovery","incident-command","skill-registry"}
            if capability_id not in allowed: raise HTTPException(status_code=404,detail="unknown capability")
            pp=CapabilityPassport.create(capability_id,"1.0.0",["sara-unified"],[f"{capability_id}:use"])
            signed=self.signer.sign_json(pp.payload())
            return {"passport":pp.payload(),"signature_b64":signed.signature_b64}
        @api.post("/v1/jury/deliberate")
        def deliberate(req:JuryRequest):
            result=self.jury.deliberate([JuryOpinion(o.model_id,o.conclusion,o.confidence,o.evidence_refs) for o in req.opinions])
            return {"resolution":result.resolution,"agreements":list(result.agreements),"disagreements":list(result.disagreements),"unresolved_questions":list(result.unresolved_questions)}
        @api.post("/v1/incidents")
        def create_incident(req:IncidentRequest,authorization:str|None=Header(default=None)):
            roles=self._roles_from_header(authorization)
            if not self.authorizer.allowed(roles,"recovery:execute"): raise HTTPException(status_code=401,detail="unauthorized")
            incident=self.incidents.create(req.title,req.severity,req.affected)
            self.audit.append("api","INCIDENT_CREATED",{"incident_id":incident.incident_id,"severity":incident.severity,"affected":sorted(incident.affected_entities)})
            return {"incident_id":incident.incident_id,"title":incident.title,"severity":incident.severity,"containment_state":incident.containment_state,"affected":sorted(incident.affected_entities)}
        @api.post("/v1/counterfactual/simulate")
        def simulate(req:CounterfactualRequest): return self.counterfactual.simulate(req.baseline,req.changes).__dict__
        @api.post("/v1/recovery/{action}")
        def recover(action:str,req:RecoveryRequest,authorization:str|None=Header(default=None)):
            roles=self._roles_from_header(authorization)
            if not self.authorizer.allowed(roles,"recovery:execute"): raise HTTPException(status_code=401,detail="unauthorized")
            result=self.recovery.execute(action,req.context,approved=req.approved)
            self.audit.append("api","RECOVERY_ATTEMPT",{"action":action,"executed":result.executed,"reason":result.reason})
            if not result.executed: raise HTTPException(status_code=403,detail=result.reason)
            return result.__dict__
        return api


def create_app():
    """Create the default FastAPI application for container startup."""
    settings=Settings.from_env()
    audit_path=os.getenv("SARA_AUDIT_PATH", "./sara-audit.jsonl")
    allow_local_operator=os.getenv("SARA_ALLOW_LOCAL_OPERATOR", "false").lower() == "true"
    return SARAUnified(AuditLedger(Path(audit_path)), settings=settings,allow_local_operator=allow_local_operator).api
