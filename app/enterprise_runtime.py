from fastapi import APIRouter, HTTPException

from .concentration import ConcentrationGovernor, ConcentrationRequest
from .hawkins_chaos import HawkinsChaosEngine, HawkinsChaosRequest
from .module_awareness import (
    HarmonizeRequest,
    MemoryConsolidation,
    ModuleAwarenessEngine,
    ModuleRecord,
    ModuleRegistrySnapshot,
    NarrativeEntry,
)
from .runtime_assurance import (
    ReceiptVerifyRequest,
    RuntimeAssuranceConfigurationError,
    RuntimeAssuranceEngine,
    RuntimeAssuranceRequest,
)
from .titan import (
    BusSubscribeRequest,
    DeploymentGateRequest,
    ExecuteGateRequest,
    SovereigntySweepRequest,
    TitanEngine,
    VoiceEventRequest,
)
from .user_identity_http import router as user_identity_router

router = APIRouter()
router.include_router(user_identity_router)
runtime_assurance = RuntimeAssuranceEngine()
module_awareness = ModuleAwarenessEngine()
titan = TitanEngine(module_awareness)
hawkins_chaos = HawkinsChaosEngine()
concentration_governor = ConcentrationGovernor()


@router.get("/runtime-assurance/health")
async def runtime_assurance_health():
    return {
        "status": "ok",
        "service": "sara-runtime-assurance",
        "policy": "fail_closed_claim_suppression",
    }


@router.get("/runtime-assurance/adapters")
async def runtime_assurance_adapters():
    return runtime_assurance.router_state()


@router.post("/runtime-assurance/verify-output")
async def runtime_assurance_verify_output(request: RuntimeAssuranceRequest):
    try:
        return await runtime_assurance.verify_output(request)
    except RuntimeAssuranceConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/runtime-assurance/receipt/verify")
async def runtime_assurance_verify_receipt(request: ReceiptVerifyRequest):
    try:
        return runtime_assurance.verify_receipt(request)
    except RuntimeAssuranceConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/module-awareness/health")
async def module_awareness_health():
    return module_awareness.health()


@router.post("/module-awareness/registry/load")
async def module_awareness_load(snapshot: ModuleRegistrySnapshot):
    return module_awareness.load_snapshot(snapshot)


@router.post("/module-awareness/register")
async def module_awareness_register(record: ModuleRecord):
    return module_awareness.register(record)


@router.get("/module-awareness/count")
async def module_awareness_count():
    return module_awareness.count()


@router.get("/module-awareness/awareness")
async def module_awareness_snapshot():
    return module_awareness.awareness()


@router.post("/module-awareness/baseline")
async def module_awareness_baseline():
    return module_awareness.establish_baseline()


@router.get("/module-awareness/diff")
async def module_awareness_diff():
    return module_awareness.diff()


@router.get("/nqhn/routes")
async def nqhn_routes():
    return module_awareness.routes()


@router.post("/nqhn/routes/register")
async def nqhn_register_route(body: dict):
    try:
        return module_awareness.register_route(str(body.get("alias", "")), str(body.get("canonical", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/nqhn/harmonize")
async def nqhn_harmonize(request: HarmonizeRequest):
    return module_awareness.harmonize(request)


@router.get("/qcr/temporal")
async def qcr_temporal():
    return module_awareness.temporal_context()


@router.post("/daystar/probe/{service}")
async def daystar_record_probe(service: str, body: dict):
    return module_awareness.record_probe(
        service=service,
        status=str(body.get("status", "live")),
        http_code=int(body.get("http_code", 200)),
    )


@router.get("/daystar/state")
async def daystar_state():
    return module_awareness.state()


@router.get("/daystar/drift")
async def daystar_drift(threshold_seconds: int = 600):
    return module_awareness.drift(max(1, threshold_seconds))


@router.post("/nscs/narrative/append")
async def nscs_append_narrative(entry: NarrativeEntry):
    return module_awareness.append_narrative(entry)


@router.get("/nscs/narrative/{session_id}")
async def nscs_get_narrative(session_id: str, limit: int = 50):
    return module_awareness.get_narrative(session_id, max(1, min(limit, 200)))


@router.post("/nscs/consolidate")
async def nscs_consolidate(request: MemoryConsolidation):
    return module_awareness.consolidate(request)


@router.get("/nscs/continuity/{session_id}")
async def nscs_continuity(session_id: str):
    return module_awareness.continuity(session_id)


@router.get("/sge/audit")
async def sge_audit():
    return module_awareness.audit()


@router.get("/sge/audit/{service_id}")
async def sge_audit_single(service_id: str):
    try:
        return module_awareness.audit(service_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"{service_id} not in registry") from exc


@router.post("/sge/remediate/{service_id}")
async def sge_remediate(service_id: str):
    try:
        return module_awareness.remediation_patch(service_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"{service_id} not in registry") from exc


@router.get("/titan/health")
async def titan_health():
    return titan.health()


@router.get("/hawkins-chaos/health")
async def hawkins_chaos_health():
    return hawkins_chaos.health()


@router.post("/hawkins-chaos/analyze")
async def hawkins_chaos_analyze(request: HawkinsChaosRequest):
    return hawkins_chaos.analyze(request)


@router.get("/concentration/health")
async def concentration_health():
    return concentration_governor.health()


@router.post("/concentration/analyze")
async def concentration_analyze(request: ConcentrationRequest):
    return concentration_governor.analyze(request)


@router.post("/titan/voice/emit")
async def titan_emit(request: VoiceEventRequest):
    try:
        return titan.emit(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/titan/voice/verify")
async def titan_verify(event: dict):
    return titan.verify_event(event)


@router.get("/titan/voice/chain/{chain_id}")
async def titan_chain(chain_id: str):
    audit = titan.audit_chain(chain_id)
    return {"chain_id": chain_id, "events": titan.chains.get(chain_id, []), **audit}


@router.post("/titan/bus/publish")
async def titan_bus_publish(event: dict):
    return titan.publish(event)


@router.post("/titan/bus/subscribe")
async def titan_bus_subscribe(request: BusSubscribeRequest):
    try:
        return titan.subscribe(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/titan/bus/subscribers")
async def titan_bus_subscribers():
    return {"subscribers": titan.subscribers}


@router.get("/titan/bus/sequence/{chain_id}")
async def titan_bus_sequence(chain_id: str):
    return titan.sequence_status(chain_id)


@router.post("/titan/deploy/gate")
async def titan_deployment_gate(request: DeploymentGateRequest):
    result = titan.deployment_gate(request)
    if not result.get("approved"):
        raise HTTPException(status_code=403, detail=result)
    return result


@router.get("/titan/deploy/gates")
async def titan_deployment_gates():
    return {"gate_count": len(titan.deployment_gates), "gates": titan.deployment_gates}


@router.post("/titan/apex/audit/{chain_id}")
async def titan_apex_audit(chain_id: str):
    return titan.audit_chain(chain_id)


@router.post("/titan/apex/execute/gate")
async def titan_apex_execute_gate(request: ExecuteGateRequest):
    result = titan.execute_gate(request)
    if not result.get("execute_authorized"):
        raise HTTPException(status_code=403 if "APPROVED" in result.get("reason", "") else 422, detail=result)
    return result


@router.post("/titan/apex/sovereignty/sweep")
async def titan_sovereignty_sweep(request: SovereigntySweepRequest):
    return titan.sovereignty_sweep(request)
