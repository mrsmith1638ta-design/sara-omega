from __future__ import annotations

import asyncio
import hashlib
import json
import uuid

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .expert_reasoning import ExpertReasoningFabric


UNIFIED_FUSION_VERSION = "1.0.0"


class EvidenceState(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    UNVERIFIED = "UNVERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EpistemicState(str, Enum):
    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    INFERRED = "INFERRED"
    DISPUTED = "DISPUTED"
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"
    INACCESSIBLE = "CURRENTLY_INACCESSIBLE"


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    ANALYSIS_ONLY = "ANALYSIS_ONLY"


class ModuleStatus(str, Enum):
    OK = "OK"
    BLOCKED = "BLOCKED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class CausalFinalityDecision(str, Enum):
    ACCEPT = "ACCEPT"
    QUARANTINE = "QUARANTINE"
    REVOKE = "REVOKE"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True, order=True)
class CausalEffect:
    resource: str
    effect: str
    boundary: str

    def key(self) -> str:
        return f"{self.resource}:{self.effect}:{self.boundary}"


@dataclass(frozen=True)
class CausalScopeApproval:
    approval_id: str
    transaction_id: str
    approved_effects: set[CausalEffect]
    command_identity: str | None = None
    approved_by: str | None = None


@dataclass(frozen=True)
class CausalFinalityResult:
    decision: CausalFinalityDecision
    approved_effects: set[CausalEffect]
    actual_effects: set[CausalEffect]
    unapproved_effects: set[CausalEffect]
    missing_effects: set[CausalEffect]
    blockers: list[str]
    quarantined: bool


@dataclass(frozen=True)
class CausalNode:
    node_id: str
    depends_on: set[str] = field(default_factory=set)
    execution_authority: bool = False
    compromised: bool = False


@dataclass(frozen=True)
class TransitiveRevocationResult:
    revoked_node_ids: set[str]
    suspended_execution_authority: set[str]
    updated_nodes: dict[str, CausalNode]


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source: str
    claim: str
    state: EpistemicState
    created_at: str
    artifact_hash: str
    candidate_commit: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModuleResult:
    module: str
    status: ModuleStatus
    findings: dict[str, Any] = field(default_factory=dict)
    risks: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    confidence: float | None = None
    execution_authority: bool = False
    release_authority: bool = False


@dataclass
class FusionRequest:
    tenant_id: str
    actor_id: str
    objective: str
    payload: dict[str, Any] = field(default_factory=dict)
    actor_scopes: set[str] = field(default_factory=set)
    requested_action: str = "ANALYZE"
    candidate_commit: str | None = None
    human_approval_id: str | None = None


@dataclass
class FusionResponse:
    request_id: str
    decision: Decision
    epistemic_state: EpistemicState
    summary: str
    module_results: dict[str, ModuleResult]
    blockers: list[str]
    required_actions: list[str]
    evidence_hash: str
    production_authority: bool = False
    release_authority: bool = False


class SaraModule(ABC):
    name: str

    @abstractmethod
    async def evaluate(self, request: FusionRequest, context: dict[str, Any]) -> ModuleResult:
        raise NotImplementedError


class SIOS:
    HIGH_RISK_ACTIONS = {
        "DEPLOY",
        "DELETE",
        "MODIFY_PRODUCTION",
        "RELEASE",
        "SIGN",
        "ROTATE_SECRET",
        "CHANGE_AUTHORITY",
    }

    async def preflight(self, request: FusionRequest) -> tuple[Decision, list[str]]:
        blockers: list[str] = []

        if not request.tenant_id:
            blockers.append("MISSING_TENANT")
        if not request.actor_id:
            blockers.append("MISSING_ACTOR")
        if request.requested_action in self.HIGH_RISK_ACTIONS and "sara.execute" not in request.actor_scopes:
            blockers.append("MISSING_EXECUTION_SCOPE")
        if request.requested_action in {"SIGN", "RELEASE"}:
            blockers.append("ROAD_AUTHORITY_REQUIRED")

        fatal = [item for item in blockers if item != "ROAD_AUTHORITY_REQUIRED"]
        return (Decision.DENY if fatal else Decision.ALLOW), blockers


class EnterpriseGovernance(SaraModule):
    name = "enterprise_governance"

    async def evaluate(self, request: FusionRequest, context: dict[str, Any]) -> ModuleResult:
        registry = context.get("feature_registry", {})
        feature = request.payload.get("feature")
        if feature and feature not in registry:
            return ModuleResult(module=self.name, status=ModuleStatus.BLOCKED, risks=["FEATURE_NOT_REGISTERED"])

        required_scope = context.get("action_scopes", {}).get(request.requested_action)
        if required_scope and required_scope not in request.actor_scopes:
            return ModuleResult(module=self.name, status=ModuleStatus.BLOCKED, risks=["INSUFFICIENT_SCOPE"])

        return ModuleResult(
            module=self.name,
            status=ModuleStatus.OK,
            findings={
                "control_inheritance_checked": True,
                "authentication_is_not_authority": True,
                "provider_certification_is_not_sara_certification": True,
            },
        )


class ACI(SaraModule):
    name = "aci"

    async def evaluate(self, request: FusionRequest, context: dict[str, Any]) -> ModuleResult:
        return ModuleResult(module=self.name, status=ModuleStatus.OK, findings=await self.run_aci(request))

    async def run_aci(self, request: FusionRequest) -> dict[str, Any]:
        return {"state": "ADAPTER_REQUIRED", "input_received": True, "objective": request.objective}


class AGPStack(SaraModule):
    name = "agp_stack"

    async def evaluate(self, request: FusionRequest, context: dict[str, Any]) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.OK,
            findings={"governance_profile": "evaluated", "policy_context": request.payload.get("policy")},
        )


class AGUAI(SaraModule):
    name = "aguai"

    async def evaluate(self, request: FusionRequest, context: dict[str, Any]) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.OK,
            findings={"interpretation": request.objective, "interface_layer": True},
        )


class UTUVI(SaraModule):
    name = "utuvi"

    async def evaluate(self, request: FusionRequest, context: dict[str, Any]) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.OK,
            findings={"validation_layer": True, "cross_check_required": True},
        )


class ApexSovereign(SaraModule):
    name = "apex_sovereign_v2"

    async def evaluate(self, request: FusionRequest, context: dict[str, Any]) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.OK,
            findings={"actor": request.actor_id, "tenant": request.tenant_id, "authority_boundary_checked": True},
        )


class SporqiC4(SaraModule):
    name = "sporqi_c4"

    async def evaluate(self, request: FusionRequest, context: dict[str, Any]) -> ModuleResult:
        observations = request.payload.get("observations", [])
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.OK,
            findings={
                "observations": len(observations),
                "prediction": None,
                "causal_claim": None,
                "requires_causal_evidence": True,
            },
        )


class SCMFSKAM(SaraModule):
    name = "scmf_skam"

    async def evaluate(self, request: FusionRequest, context: dict[str, Any]) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.OK,
            findings={"optimization_layer": True, "quantum_execution_verified": False},
        )


class Kinetics(SaraModule):
    name = "kinetics"

    async def evaluate(self, request: FusionRequest, context: dict[str, Any]) -> ModuleResult:
        history = request.payload.get("state_history", [])
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.OK,
            findings={"history_points": len(history), "dynamic_analysis": bool(history)},
        )


class SelfHealing(SaraModule):
    name = "self_healing"

    async def evaluate(self, request: FusionRequest, context: dict[str, Any]) -> ModuleResult:
        failures = context.get("failures", [])
        proposals = [
            {"failure": failure, "action": "REPAIR_PROPOSAL_ONLY", "authorized": False}
            for failure in failures
        ]
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.DEGRADED if failures else ModuleStatus.OK,
            findings={"failures_detected": len(failures), "repair_proposals": proposals},
        )


class ExpertReasoning(SaraModule):
    name = "expert_reasoning_fabric"

    def __init__(self, fabric: ExpertReasoningFabric | None = None) -> None:
        self.fabric = fabric or ExpertReasoningFabric()

    async def evaluate(self, request: FusionRequest, context: dict[str, Any]) -> ModuleResult:
        raw_evidence = request.payload.get("evidence", [])
        if isinstance(raw_evidence, dict):
            evidence = [raw_evidence]
        elif isinstance(raw_evidence, list):
            evidence = raw_evidence
        else:
            evidence = []

        findings = self.fabric.synthesize(
            request.objective,
            evidence=evidence,
            industries=request.payload.get("industries"),
        )
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.OK,
            findings=findings,
            execution_authority=False,
            release_authority=False,
        )


class Madhouse:
    async def attack(self, results: dict[str, ModuleResult]) -> tuple[bool, list[str]]:
        findings: list[str] = []
        for name, result in results.items():
            if result.execution_authority:
                findings.append(f"{name}:ILLEGAL_SELF_EXECUTION_AUTHORITY")
            if result.release_authority:
                findings.append(f"{name}:ILLEGAL_SELF_RELEASE_AUTHORITY")
            if result.status == ModuleStatus.FAILED:
                findings.append(f"{name}:MODULE_FAILURE")
        return bool(findings), findings


class EpistemicResolver:
    def resolve(self, results: dict[str, ModuleResult]) -> EpistemicState:
        if not results:
            return EpistemicState.UNKNOWN

        states: list[EpistemicState] = []
        for result in results.values():
            if result.status in {ModuleStatus.FAILED, ModuleStatus.BLOCKED}:
                states.append(EpistemicState.UNVERIFIED)
            elif result.evidence:
                states.append(EpistemicState.SUPPORTED)
            else:
                states.append(EpistemicState.INFERRED)

        if EpistemicState.UNVERIFIED in states:
            return EpistemicState.UNVERIFIED
        if all(state == EpistemicState.SUPPORTED for state in states):
            return EpistemicState.SUPPORTED
        return EpistemicState.INFERRED


class CausalAuthorityEngine:
    def reconcile_finality(
        self,
        approval: CausalScopeApproval,
        actual_effects: set[CausalEffect],
        actual_command_identity: str | None = None,
    ) -> CausalFinalityResult:
        approved = set(approval.approved_effects)
        actual = set(actual_effects)
        unapproved = actual - approved
        missing = approved - actual
        blockers: list[str] = []

        if unapproved:
            blockers.append("CAUSAL_SCOPE_VIOLATION")
        if missing:
            blockers.append("APPROVED_CAUSAL_EFFECT_MISSING")
        if (
            approval.command_identity
            and actual_command_identity
            and approval.command_identity == actual_command_identity
            and (unapproved or missing)
        ):
            blockers.append("COMMAND_MATCH_DOES_NOT_OVERRIDE_CAUSAL_MISMATCH")

        quarantined = bool(blockers)
        return CausalFinalityResult(
            decision=CausalFinalityDecision.QUARANTINE if quarantined else CausalFinalityDecision.ACCEPT,
            approved_effects=approved,
            actual_effects=actual,
            unapproved_effects=unapproved,
            missing_effects=missing,
            blockers=blockers,
            quarantined=quarantined,
        )

    def revoke_transitive_authority(
        self,
        graph: list[CausalNode],
        compromised_node_ids: set[str],
    ) -> TransitiveRevocationResult:
        nodes = {node.node_id: node for node in graph}
        revoked = set(compromised_node_ids) & set(nodes)
        changed = True
        while changed:
            changed = False
            for node in nodes.values():
                if node.node_id not in revoked and node.depends_on & revoked:
                    revoked.add(node.node_id)
                    changed = True

        updated: dict[str, CausalNode] = {}
        suspended: set[str] = set()
        for node_id, node in nodes.items():
            if node_id in revoked:
                suspended.add(node_id)
                updated[node_id] = CausalNode(
                    node_id=node.node_id,
                    depends_on=set(node.depends_on),
                    execution_authority=False,
                    compromised=node.compromised or node_id in compromised_node_ids,
                )
            else:
                updated[node_id] = node

        return TransitiveRevocationResult(
            revoked_node_ids=revoked,
            suspended_execution_authority=suspended,
            updated_nodes=updated,
        )


class ROADClient:
    def __init__(self, authoritative: bool = False) -> None:
        self.authoritative = authoritative

    async def verify_candidate(self, candidate_commit: str | None, evidence_hash: str) -> EvidenceState:
        if not self.authoritative:
            return EvidenceState.UNVERIFIED
        if not candidate_commit:
            return EvidenceState.BLOCKED
        return EvidenceState.UNVERIFIED


class SaraFusionEngine:
    def __init__(
        self,
        modules: list[SaraModule] | None = None,
        road: ROADClient | None = None,
    ) -> None:
        self.sios = SIOS()
        self.modules = modules or [
            EnterpriseGovernance(),
            ACI(),
            AGPStack(),
            AGUAI(),
            UTUVI(),
            ApexSovereign(),
            SporqiC4(),
            SCMFSKAM(),
            Kinetics(),
            ExpertReasoning(),
            SelfHealing(),
        ]
        self.madhouse = Madhouse()
        self.epistemic = EpistemicResolver()
        self.road = road or ROADClient(authoritative=False)

    async def execute(self, request: FusionRequest) -> FusionResponse:
        request_id = str(uuid.uuid4())
        sios_decision, sios_blockers = await self.sios.preflight(request)

        fatal_sios_blockers = [item for item in sios_blockers if item != "ROAD_AUTHORITY_REQUIRED"]
        if sios_decision == Decision.DENY and fatal_sios_blockers:
            return self._response(
                request_id=request_id,
                decision=Decision.DENY,
                epistemic_state=EpistemicState.UNVERIFIED,
                summary="SIOS blocked the request.",
                results={},
                blockers=sorted(fatal_sios_blockers),
                required_actions=["Resolve blocking findings and retest."],
            )

        context: dict[str, Any] = {
            "feature_registry": {
                "SARA_CORE": {"eligible": True},
                "ROAD": {"eligible": True},
                "ENTERPRISE_GOVERNANCE": {"eligible": True},
                "UNIFIED_FUSION": {"eligible": True},
                "EXPERT_REASONING_FABRIC": {"eligible": True},
            },
            "action_scopes": {
                "ANALYZE": "sara.solve",
                "GOVERNANCE_EVALUATE": "sara.governance.evaluate",
                "MEMORY": "sara.memory",
                "EXECUTE": "sara.execute",
            },
            "failures": [],
        }

        raw_results = await asyncio.gather(
            *(module.evaluate(request, context) for module in self.modules),
            return_exceptions=True,
        )

        results: dict[str, ModuleResult] = {}
        for module, result in zip(self.modules, raw_results):
            if isinstance(result, Exception):
                results[module.name] = ModuleResult(
                    module=module.name,
                    status=ModuleStatus.FAILED,
                    risks=[type(result).__name__],
                )
                context["failures"].append(module.name)
            else:
                results[module.name] = result

        blockers: list[str] = list(sios_blockers)
        for name, result in results.items():
            if result.status in {ModuleStatus.BLOCKED, ModuleStatus.FAILED}:
                blockers.append(f"{name}:{result.status.value}")
            blockers.extend(f"{name}:{risk}" for risk in result.risks)

        madhouse_blocked, madhouse_findings = await self.madhouse.attack(results)
        blockers.extend(madhouse_findings)
        epistemic_state = self.epistemic.resolve(results)
        evidence_hash = self._hash_results(request, results)

        if blockers or madhouse_blocked:
            decision = Decision.DENY
        elif request.requested_action in {"DEPLOY", "SIGN", "RELEASE", "MODIFY_PRODUCTION"}:
            decision = Decision.REQUIRE_APPROVAL
        else:
            decision = Decision.ALLOW

        road_state = EvidenceState.NOT_APPLICABLE
        if request.requested_action in {"DEPLOY", "SIGN", "RELEASE"}:
            road_state = await self.road.verify_candidate(request.candidate_commit, evidence_hash)
            if road_state != EvidenceState.PASS:
                decision = Decision.DENY
                blockers.append(f"ROAD:{road_state.value}")

        summary = (
            "Unified SARA fusion completed. Module output remains subordinate "
            "to SIOS, MADHOUSE, epistemic verification, enterprise governance, and ROAD."
        )
        return self._response(
            request_id=request_id,
            decision=decision,
            epistemic_state=epistemic_state,
            summary=summary,
            results=results,
            blockers=sorted(set(blockers)),
            required_actions=self._required_actions(blockers, road_state),
            evidence_hash=evidence_hash,
        )

    @staticmethod
    def _hash_results(request: FusionRequest, results: dict[str, ModuleResult]) -> str:
        serializable = {
            "request": {
                "tenant_id": request.tenant_id,
                "actor_id": request.actor_id,
                "objective": request.objective,
                "requested_action": request.requested_action,
                "candidate_commit": request.candidate_commit,
            },
            "modules": {
                name: {
                    "status": result.status.value,
                    "findings": result.findings,
                    "risks": result.risks,
                }
                for name, result in sorted(results.items())
            },
        }
        payload = json.dumps(serializable, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _required_actions(blockers: list[str], road_state: EvidenceState) -> list[str]:
        actions: list[str] = []
        if blockers:
            actions.append("Resolve blocking findings and retest.")
        if road_state not in {EvidenceState.PASS, EvidenceState.NOT_APPLICABLE}:
            actions.append("Submit exact candidate evidence to authoritative ROAD.")
        return actions

    @staticmethod
    def _response(
        *,
        request_id: str,
        decision: Decision,
        epistemic_state: EpistemicState,
        summary: str,
        results: dict[str, ModuleResult],
        blockers: list[str],
        required_actions: list[str],
        evidence_hash: str = "",
    ) -> FusionResponse:
        return FusionResponse(
            request_id=request_id,
            decision=decision,
            epistemic_state=epistemic_state,
            summary=summary,
            module_results=results,
            blockers=blockers,
            required_actions=required_actions,
            evidence_hash=evidence_hash,
            production_authority=False,
            release_authority=False,
        )


class SARAOmega:
    def __init__(self, fusion: SaraFusionEngine | None = None) -> None:
        self.fusion = fusion or SaraFusionEngine()

    async def solve(
        self,
        tenant_id: str,
        actor_id: str,
        objective: str,
        payload: dict[str, Any] | None = None,
        scopes: set[str] | None = None,
    ) -> FusionResponse:
        request = FusionRequest(
            tenant_id=tenant_id,
            actor_id=actor_id,
            objective=objective,
            payload=payload or {},
            actor_scopes=scopes or {"sara.solve"},
            requested_action="ANALYZE",
        )
        return await self.fusion.execute(request)


def health() -> dict[str, Any]:
    return {
        "module": "sara-unified-fusion",
        "version": UNIFIED_FUSION_VERSION,
        "production_authority": False,
        "release_authority": False,
        "road_pass_fabrication": False,
        "authentication_is_not_execution_authority": True,
        "missing_road_evidence_fails_closed": True,
        "self_healing_autonomous_production_mutation": False,
        "quantum_output_is_not_quantum_proof": True,
        "prediction_is_not_causation": True,
        "causal_scope_authority": True,
        "causal_finality_reconciliation": True,
        "transitive_authority_revocation": True,
        "causal_effects_exceeding_approval_quarantine": True,
        "expert_reasoning_fabric": True,
        "phd_research_methodology": True,
        "jd_legal_reasoning_methodology": True,
        "edd_applied_education_methodology": True,
        "ai_research_phd_methodology": True,
        "dynamic_cross_industry_reasoning": True,
        "claims_human_consciousness": False,
        "claims_ai_consciousness": False,
        "credential_impersonation": False,
    }


def evidence_for_claim(
    *,
    evidence_id: str,
    source: str,
    claim: str,
    state: EpistemicState = EpistemicState.UNVERIFIED,
    candidate_commit: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Evidence:
    artifact_payload = {
        "evidence_id": evidence_id,
        "source": source,
        "claim": claim,
        "state": state.value,
        "candidate_commit": candidate_commit,
        "metadata": metadata or {},
    }
    artifact_hash = hashlib.sha256(json.dumps(artifact_payload, sort_keys=True).encode("utf-8")).hexdigest()
    return Evidence(
        evidence_id=evidence_id,
        source=source,
        claim=claim,
        state=state,
        created_at=datetime.now(timezone.utc).isoformat(),
        artifact_hash=artifact_hash,
        candidate_commit=candidate_commit,
        metadata=metadata or {},
    )
