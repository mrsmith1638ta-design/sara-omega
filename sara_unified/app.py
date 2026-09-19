from pathlib import Path
import hashlib
import os
from fastapi import FastAPI, Header, HTTPException, Response
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
from sara_unified.api.schemas import RecoveryRequest, CounterfactualRequest, JuryRequest, IncidentRequest, TwinObservationRequest, VoiceSynthesisRequest
from sara_unified.config import Settings
from sara_unified.governance.asymmetric_signing import DualKmsSignerClient
from sara_unified.governance.enforcement import (
    EnforcementProfile,
    GovernanceEnforcementError,
    ProductionEnforcementBoundary,
)
from sara_unified.voice.client import PiperVoiceClient, VoiceSynthesisError
from sara_unified.voice.profile import SARA_VOICE_PROFILE


GOV_TWIN_OBSERVE = EnforcementProfile(
    action="twin.observe",
    tool="digital-twin",
    capability="twin:write",
    from_state="OBSERVED",
    to_state="CANONICAL",
    reversible=True,
    production=True,
)

GOV_INCIDENT_CREATE = EnforcementProfile(
    action="incident.create",
    tool="incident-commander",
    capability="incident:create",
    from_state="NONE",
    to_state="OPEN",
    reversible=True,
    production=True,
)

GOV_RECOVERY_EXECUTE = EnforcementProfile(
    action="recovery.execute",
    tool="recovery-registry",
    capability="recovery:execute",
    from_state="DEGRADED",
    to_state="RECOVERING",
    reversible=True,
    production=True,
    high_impact_domain=True,
)

GOV_VOICE_SYNTHESIZE = EnforcementProfile(
    action="voice.synthesize",
    tool="voice-service",
    capability="voice:synthesize",
    from_state="TEXT_VALIDATED",
    to_state="AUDIO_SYNTHESIZED",
    reversible=True,
    production=True,
    external_network_access=True,
)


class SARAUnified:
    def __init__(
        self,
        audit,
        authorizer=None,
        settings=None,
        allow_local_operator=True,
        voice_client=None,
        governance_boundary=None,
    ):
        self.settings=settings or Settings()
        self.allow_local_operator=allow_local_operator
        self.audit=audit
        self.authorizer=authorizer or Authorizer({
            "operator":{
                "recovery:execute",
                "twin:read",
                "twin:write",
                "incident:create",
                "counterfactual:run",
                "voice:synthesize",
            }
        })
        signing_key=(
            self.settings.governance_signing_key.encode("utf-8")
            if self.settings.governance_signing_key
            else None
        )
        evidence_signer=None
        if (
            self.settings.governance_signer_url
            and self.settings.governance_signer_token
            and self.settings.governance_ed25519_key_id
            and self.settings.governance_ml_dsa_key_id
        ):
            evidence_signer=DualKmsSignerClient(
                base_url=self.settings.governance_signer_url,
                bearer_token=self.settings.governance_signer_token,
                ed25519_key_id=self.settings.governance_ed25519_key_id,
                ml_dsa_key_id=self.settings.governance_ml_dsa_key_id,
                timeout_seconds=self.settings.governance_signer_timeout_seconds,
                require_kms_backend=True,
            )
        self.governance=governance_boundary or ProductionEnforcementBoundary(
            self.audit,
            signing_key=signing_key,
            evidence_signer=evidence_signer,
            required=self.settings.governance_enforcement_required,
            tenant_id=self.settings.governance_tenant_id,
        )
        self.twin=DigitalTwin(); self.health=HealthAggregator(); self.recovery=RecoveryRegistry(); self.services=ServiceRegistry(); self.incidents=IncidentCommander(self.twin)
        self.counterfactual=CounterfactualEngine(); self.jury=ModelJury(); self.gaps=KnowledgeGapRadar(); self.fusion=EvidenceFusion(); self.skills=SkillRegistry(); self.signer=Ed25519Signer.generate()
        self.voice_client=voice_client
        if self.voice_client is None and self.settings.voice_enabled:
            self.voice_client=PiperVoiceClient(
                self.settings.piper_service_url,
                self.settings.piper_service_token,
                timeout_seconds=self.settings.voice_timeout_seconds,
            )
        self.recovery.register(RecoveryAction("restart",True,lambda ctx:{"accepted":True,"service":ctx.get("service")}))
        self.api=self._build_api()

    @classmethod
    def local(cls,audit_path="./sara-audit.jsonl"): return cls(AuditLedger(Path(audit_path)))

    def _roles_from_header(self,authorization):
        if not authorization or not authorization.startswith("Bearer "): return set()
        token=authorization[7:].strip()
        return {"operator"} if self.allow_local_operator and token=="local-operator" else set()

    def _capabilities_for_roles(self,roles):
        capabilities=set()
        for role in roles:
            capabilities.update(self.authorizer.grants.get(role,set()))
        return capabilities

    @staticmethod
    def _actor_id_for_roles(roles):
        return "role:" + ",".join(sorted(roles)) if roles else ""

    def _authorize_effect(
        self,
        *,
        profile,
        roles,
        resource,
        human_approval_id=None,
        affected_records=0,
        financial_value_usd=0.0,
        contains_sensitive_data=False,
        anomaly_score=0.0,
        autonomous=False,
        metadata=None,
    ):
        try:
            return self.governance.authorize(
                profile=profile,
                actor_id=self._actor_id_for_roles(roles),
                actor_type="api",
                capabilities=self._capabilities_for_roles(roles),
                input_provenance_ok=True,
                resource=resource,
                human_approval_id=human_approval_id,
                affected_records=affected_records,
                financial_value_usd=financial_value_usd,
                contains_sensitive_data=contains_sensitive_data,
                anomaly_score=anomaly_score,
                autonomous=autonomous,
                metadata=metadata or {},
            )
        except GovernanceEnforcementError as exc:
            detail={
                "error":"governance_execution_blocked",
                "message":str(exc),
            }
            if exc.decision is not None:
                detail["decision"]=exc.decision.value
            if exc.evidence_hash:
                detail["evidence_hash"]=exc.evidence_hash
            raise HTTPException(status_code=exc.status_code,detail=detail) from exc

    def _build_api(self):
        api=FastAPI(title="SARA Unified Ecosystem",version="3.2.1+unified")

        @api.middleware("http")
        async def enforce_request_size(request, call_next):
            content_length=request.headers.get("content-length")
            if content_length is not None and int(content_length) > self.settings.max_request_bytes:
                return JSONResponse(status_code=413,content={"detail":"request body too large"})
            return await call_next(request)

        @api.get("/health")
        def health():
            return {
                "alive":True,
                "audit_chain_valid":self.audit.verify(),
                "governance_enforcement_ready":self.governance.ready,
                "governance_enforcement_required":self.settings.governance_enforcement_required,
                "version":"3.2.1+unified",
            }

        @api.get("/readyz")
        def ready():
            self.health.audit_chain_valid=self.audit.verify()
            status=dict(self.health.status())
            governance_ready=self.governance.ready
            status["governance_enforcement_ready"]=governance_ready
            status["governance_enforcement_required"]=self.settings.governance_enforcement_required
            if self.settings.governance_enforcement_required and not governance_ready:
                status["ready"]=False
            return JSONResponse(status_code=200 if status["ready"] else 503,content=status)

        @api.get("/v1/capabilities")
        def capabilities(): return {"capabilities":["evidence-fusion","digital-twin","model-jury","counterfactual","gap-radar","governed-recovery","incident-command","skill-registry","voice-synthesis","production-governance-enforcement"]}

        @api.get("/v1/voice/profile")
        def voice_profile():
            return SARA_VOICE_PROFILE.public_metadata()

        @api.post("/v1/voice/synthesize")
        def synthesize_voice(req:VoiceSynthesisRequest,authorization:str|None=Header(default=None)):
            roles=self._roles_from_header(authorization)
            if not self.authorizer.allowed(roles,"voice:synthesize"):
                raise HTTPException(status_code=401,detail="unauthorized")
            if not self.settings.voice_enabled:
                raise HTTPException(status_code=503,detail="voice synthesis disabled")
            text=req.text.strip()
            if not text:
                raise HTTPException(status_code=422,detail="voice text must not be empty")
            if len(text) > self.settings.voice_max_characters:
                raise HTTPException(status_code=422,detail="voice text exceeds configured character limit")
            if self.voice_client is None:
                raise HTTPException(status_code=503,detail="voice synthesis unavailable")
            text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest()
            evidence=self._authorize_effect(
                profile=GOV_VOICE_SYNTHESIZE,
                roles=roles,
                resource="voice-service",
                metadata={
                    "profile_id":SARA_VOICE_PROFILE.profile_id,
                    "character_count":len(text),
                    "text_sha256":text_sha256,
                },
            )
            try:
                audio=self.voice_client.synthesize(text)
            except VoiceSynthesisError as exc:
                raise HTTPException(status_code=502,detail="voice synthesis failed") from exc
            self.audit.append(
                "api",
                "VOICE_SYNTHESIZED",
                {
                    "profile_id": SARA_VOICE_PROFILE.profile_id,
                    "character_count": len(text),
                    "text_sha256": text_sha256,
                    "governance_evidence_hash": evidence.evidence_hash,
                },
            )
            return Response(
                content=audio,
                media_type="audio/wav",
                headers={"X-SARA-Governance-Evidence":evidence.evidence_hash},
            )

        @api.get("/v1/twin")
        def twin_snapshot(): return {"entities": self.twin.snapshot()}

        @api.post("/v1/twin/observe")
        def twin_observe(req:TwinObservationRequest,authorization:str|None=Header(default=None)):
            roles=self._roles_from_header(authorization)
            if not self.authorizer.allowed(roles,"twin:write"): raise HTTPException(status_code=401,detail="unauthorized")
            if not req.verified: raise HTTPException(status_code=422,detail="unverified observations cannot mutate canonical twin")
            evidence=self._authorize_effect(
                profile=GOV_TWIN_OBSERVE,
                roles=roles,
                resource=req.entity_id,
                affected_records=1,
                metadata={"source":req.source},
            )
            self.twin.observe(req.entity_id,req.state,True,req.source)
            self.audit.append(
                "api",
                "TWIN_OBSERVED",
                {
                    "entity_id":req.entity_id,
                    "source":req.source,
                    "governance_evidence_hash":evidence.evidence_hash,
                },
            )
            return {
                "accepted":True,
                "entity_id":req.entity_id,
                "governance_evidence_hash":evidence.evidence_hash,
            }

        @api.get("/v1/evidence/audit-status")
        def audit_status(): return {"valid": self.audit.verify()}

        @api.get("/v1/passports/{capability_id}")
        def passport(capability_id:str):
            allowed={"evidence-fusion","digital-twin","model-jury","counterfactual","gap-radar","governed-recovery","incident-command","skill-registry","voice-synthesis","production-governance-enforcement"}
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
            if not self.authorizer.allowed(roles,"incident:create"): raise HTTPException(status_code=401,detail="unauthorized")
            evidence=self._authorize_effect(
                profile=GOV_INCIDENT_CREATE,
                roles=roles,
                resource="incident-registry",
                affected_records=len(req.affected),
                metadata={"severity":req.severity,"affected_count":len(req.affected)},
            )
            incident=self.incidents.create(req.title,req.severity,req.affected)
            self.audit.append(
                "api",
                "INCIDENT_CREATED",
                {
                    "incident_id":incident.incident_id,
                    "severity":incident.severity,
                    "affected":sorted(incident.affected_entities),
                    "governance_evidence_hash":evidence.evidence_hash,
                },
            )
            return {
                "incident_id":incident.incident_id,
                "title":incident.title,
                "severity":incident.severity,
                "containment_state":incident.containment_state,
                "affected":sorted(incident.affected_entities),
                "governance_evidence_hash":evidence.evidence_hash,
            }

        @api.post("/v1/counterfactual/simulate")
        def simulate(req:CounterfactualRequest): return self.counterfactual.simulate(req.baseline,req.changes).__dict__

        @api.post("/v1/recovery/{action}")
        def recover(action:str,req:RecoveryRequest,authorization:str|None=Header(default=None)):
            roles=self._roles_from_header(authorization)
            if not self.authorizer.allowed(roles,"recovery:execute"): raise HTTPException(status_code=401,detail="unauthorized")
            service=str(req.context.get("service","unknown"))
            evidence=self._authorize_effect(
                profile=GOV_RECOVERY_EXECUTE,
                roles=roles,
                resource=service,
                human_approval_id="api-recovery-approval" if req.approved else None,
                metadata={"recovery_action":action},
            )
            result=self.recovery.execute(action,req.context,approved=req.approved)
            self.audit.append(
                "api",
                "RECOVERY_ATTEMPT",
                {
                    "action":action,
                    "executed":result.executed,
                    "reason":result.reason,
                    "governance_evidence_hash":evidence.evidence_hash,
                },
            )
            if not result.executed: raise HTTPException(status_code=403,detail=result.reason)
            payload=dict(result.__dict__)
            payload["governance_evidence_hash"]=evidence.evidence_hash
            return payload

        return api


def create_app():
    """Create the default FastAPI application for container startup."""
    settings=Settings.from_env()
    audit_path=os.getenv("SARA_AUDIT_PATH", "./sara-audit.jsonl")
    allow_local_operator=os.getenv("SARA_ALLOW_LOCAL_OPERATOR", "false").lower() == "true"
    return SARAUnified(AuditLedger(Path(audit_path)), settings=settings,allow_local_operator=allow_local_operator).api
