from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .memory import EncryptedStateStore, MemoryStoreError


ONTOLOGICAL_ANCHOR = "0aa4755159bf24d69acd4e8608445bbe"

INFRASTRUCTURE_SERVICES = {
    "provenance-chain",
    "raft-node-n1",
    "raft-node-n2",
    "raft-node-n3",
    "sara-architect-approval",
    "sara-constitutional",
    "sara-daystar",
    "sara-deployment-orchestrator",
    "sara-east-connector",
    "sara-hep-science-discovery",
    "sara-knowledge-synthesis",
    "sara-llm-api",
    "sara-module-awareness",
    "sara-nexus-arm",
    "sara-nqhn",
    "sara-nscs",
    "sara-public-registry",
    "sara-qcr",
    "sara-sge",
    "sara-sesg",
    "sara-sif-orchestrator",
    "sara-titan-apex",
    "sara-titan-controller",
    "sara-titan-voice-bus",
    "sara-voice-api",
    "sara-voice-dispatch",
    "sovereign-orchestrator",
}

DEFAULT_ROUTE_TABLE = {
    "/api/voice": "/v1/voice/text",
    "/voice/text-fast": "/v1/voice/text",
    "/v1/voice/text-fast": "/v1/voice/text",
}


class ModuleRecord(BaseModel):
    service: str
    url: str = ""
    status: str = "unknown"
    registered_at: str | None = None
    ontological_anchor: str = ONTOLOGICAL_ANCHOR
    version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModuleRegistrySnapshot(BaseModel):
    modules: list[ModuleRecord] = Field(default_factory=list)
    baseline: list[str] = Field(default_factory=list)


class HarmonizeRequest(BaseModel):
    target_service: str
    path: str
    payload: dict[str, Any] = Field(default_factory=dict)


class NarrativeEntry(BaseModel):
    session_id: str
    actor: str
    content: str
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class MemoryConsolidation(BaseModel):
    session_id: str
    summary: str
    key_facts: list[str] = Field(default_factory=list)
    strategic_intents: list[str] = Field(default_factory=list)


class ModuleAwarenessEngine:
    """Integrated module awareness, temporal context and continuity layer."""

    def __init__(self, baseline_count: int | None = None, state_store: EncryptedStateStore | None = None):
        self.baseline_count = baseline_count or int(os.getenv("SARA_MODULE_BASELINE_COUNT", "215"))
        self.registry: dict[str, ModuleRecord] = {}
        self.baseline: set[str] = set()
        self.route_table = dict(DEFAULT_ROUTE_TABLE)
        self.probe_state: dict[str, dict[str, Any]] = {}
        self.narrative: dict[str, list[dict[str, Any]]] = {}
        self.consolidations: dict[str, dict[str, Any]] = {}
        self._state_store = state_store if state_store is not None else EncryptedStateStore.from_env(required=False)
        self._suspend_persistence = True
        for service in (
            "sara-module-awareness",
            "sara-nqhn",
            "sara-qcr",
            "sara-daystar",
            "sara-nscs",
            "sara-sge",
            "sara-titan-controller",
            "sara-titan-voice-bus",
            "sara-titan-apex",
        ):
            self.register(ModuleRecord(service=service, status="integrated"))
        self._suspend_persistence = False
        if self._state_store is not None:
            persisted = self._state_store.load_json("module-awareness-v1", "state")
            if persisted is not None:
                self._restore_persisted_state(persisted)
            else:
                self._persist_state()

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "sara-module-awareness-integrated",
            "anchor": ONTOLOGICAL_ANCHOR,
            "integrated_capabilities": [
                "module_count",
                "awareness_snapshot",
                "baseline_diff",
                "query_harmonization",
                "temporal_context",
                "drift_detection",
                "continuity_memory",
                "sovereign_governance_audit",
            ],
        }

    def load_snapshot(self, snapshot: ModuleRegistrySnapshot) -> dict[str, Any]:
        self.registry = {m.service: m for m in snapshot.modules}
        self.baseline = set(snapshot.baseline)
        self._persist_state()
        return self.awareness()

    def register(self, record: ModuleRecord) -> dict[str, Any]:
        if not record.registered_at:
            record.registered_at = self._now_iso()
        self.registry[record.service] = record
        self._persist_state()
        return {"registered": True, "service": record.service, "anchor": ONTOLOGICAL_ANCHOR}

    def count(self) -> dict[str, Any]:
        services = set(self.registry)
        sovereign = sorted(s for s in services if s not in INFRASTRUCTURE_SERVICES)
        infra = sorted(services - set(sovereign))
        return {
            "total_registered": len(services),
            "infrastructure_excluded": len(infra),
            "sovereign_module_count": len(sovereign),
            "baseline": self.baseline_count,
            "delta": len(sovereign) - self.baseline_count,
            "timestamp": self._now_iso(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }

    def awareness(self) -> dict[str, Any]:
        modules = []
        for service, record in sorted(self.registry.items()):
            data = record.model_dump()
            data["is_infrastructure"] = service in INFRASTRUCTURE_SERVICES
            modules.append(data)
        return {
            "module_count": len(modules),
            "modules": modules,
            "timestamp": self._now_iso(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }

    def establish_baseline(self) -> dict[str, Any]:
        self.baseline = {s for s in self.registry if s not in INFRASTRUCTURE_SERVICES}
        self.baseline_count = len(self.baseline)
        self._persist_state()
        return {"established": True, "count": self.baseline_count, "timestamp": self._now_iso()}

    def diff(self) -> dict[str, Any]:
        current = {s for s in self.registry if s not in INFRASTRUCTURE_SERVICES}
        baseline = self.baseline or current
        return {
            "baseline_count": len(baseline),
            "current_count": len(current),
            "added": sorted(current - baseline),
            "removed": sorted(baseline - current),
            "net_delta": len(current) - len(baseline),
            "timestamp": self._now_iso(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }

    def routes(self) -> dict[str, Any]:
        return {"route_table": dict(self.route_table), "count": len(self.route_table), "anchor": ONTOLOGICAL_ANCHOR}

    def register_route(self, alias: str, canonical: str) -> dict[str, Any]:
        if not alias or not canonical:
            raise ValueError("alias and canonical are required")
        self.route_table[alias] = canonical
        self._persist_state()
        return {"registered": True, "alias": alias, "canonical": canonical, "anchor": ONTOLOGICAL_ANCHOR}

    def harmonize(self, request: HarmonizeRequest) -> dict[str, Any]:
        resolved_path = self.route_table.get(request.path, request.path)
        module = self.registry.get(request.target_service)
        target_url = f"{module.url.rstrip('/')}{resolved_path}" if module and module.url else resolved_path
        return {
            "target_service": request.target_service,
            "original_path": request.path,
            "resolved_path": resolved_path,
            "target_url": target_url,
            "payload": request.payload,
            "forwarded": False,
            "reason": "Omega integration resolves routes without forwarding during local assurance.",
            "timestamp": self._now_iso(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }

    def temporal_context(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "utc_timestamp": now.isoformat(),
            "epoch_seconds": int(now.timestamp()),
            "day_of_week": now.strftime("%A"),
            "iso_week": now.isocalendar().week,
            "anchor": ONTOLOGICAL_ANCHOR,
        }

    def record_probe(self, service: str, status: str = "live", http_code: int = 200) -> dict[str, Any]:
        state = {
            "service": service,
            "status": status,
            "http_code": http_code,
            "last_seen": self._now_iso() if status == "live" else None,
            "probed_at": self._now_iso(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }
        self.probe_state[service] = state
        self._persist_state()
        return state

    def state(self) -> dict[str, Any]:
        states = list(self.probe_state.values())
        live = sum(1 for s in states if s.get("status") == "live")
        unreachable = sum(1 for s in states if s.get("status") == "unreachable")
        return {
            "module_count": len(states),
            "live": live,
            "unreachable": unreachable,
            "degraded": len(states) - live - unreachable,
            "modules": sorted(states, key=lambda x: x.get("service", "")),
            "snapshot_at": self._now_iso(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }

    def drift(self, threshold_seconds: int = 600) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        drifted = []
        for service, data in self.probe_state.items():
            last_seen = data.get("last_seen")
            if not last_seen:
                drifted.append({"service": service, "reason": "never_probed"})
                continue
            last = datetime.fromisoformat(last_seen)
            seconds = int((now - last).total_seconds())
            if seconds > threshold_seconds:
                drifted.append({"service": service, "last_seen": last_seen, "drift_seconds": seconds})
        return {
            "drifted_count": len(drifted),
            "modules": drifted,
            "threshold_seconds": threshold_seconds,
            "checked_at": self._now_iso(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }

    def append_narrative(self, entry: NarrativeEntry) -> dict[str, Any]:
        item = {
            "entry_id": self._entry_id(entry.session_id, entry.content),
            "session_id": entry.session_id,
            "actor": entry.actor,
            "content": entry.content,
            "importance": entry.importance,
            "timestamp": self._now_iso(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }
        self.narrative.setdefault(entry.session_id, []).append(item)
        self._persist_state()
        return {"stored": True, "entry_id": item["entry_id"], "anchor": ONTOLOGICAL_ANCHOR}

    def get_narrative(self, session_id: str, limit: int = 50) -> dict[str, Any]:
        entries = sorted(
            self.narrative.get(session_id, []),
            key=lambda item: (-float(item.get("importance", 0)), str(item.get("timestamp", ""))),
        )[:limit]
        return {"session_id": session_id, "entry_count": len(entries), "entries": entries, "anchor": ONTOLOGICAL_ANCHOR}

    def consolidate(self, request: MemoryConsolidation) -> dict[str, Any]:
        doc = {
            "session_id": request.session_id,
            "summary": request.summary,
            "key_facts": request.key_facts,
            "strategic_intents": request.strategic_intents,
            "consolidated_at": self._now_iso(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }
        self.consolidations[request.session_id] = doc
        self._persist_state()
        return {"consolidated": True, "session_id": request.session_id, "fact_count": len(request.key_facts)}

    def continuity(self, session_id: str) -> dict[str, Any]:
        has_narrative = bool(self.narrative.get(session_id))
        has_consolidation = session_id in self.consolidations
        return {
            "session_id": session_id,
            "has_narrative": has_narrative,
            "has_consolidation": has_consolidation,
            "continuity_intact": has_narrative and has_consolidation,
            "checked_at": self._now_iso(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }

    def audit(self, service_id: str | None = None) -> dict[str, Any]:
        targets = [self.registry[service_id]] if service_id else list(self.registry.values())
        checks = [self._compliance_check(record) for record in targets if record]
        non_compliant = [c for c in checks if not c["compliant"]]
        return {
            "total_audited": len(checks),
            "compliant": len(checks) - len(non_compliant),
            "non_compliant": len(non_compliant),
            "violations": non_compliant,
            "audit_at": self._now_iso(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }

    def remediation_patch(self, service_id: str) -> dict[str, Any]:
        record = self.registry.get(service_id)
        if not record:
            raise KeyError(service_id)
        url = record.url.replace("667977407542", "i7iay5r2wq")
        patch = {
            "ontological_anchor": ONTOLOGICAL_ANCHOR,
            "url": url,
            "remediated_at": self._now_iso(),
            "remediated_by": "sara-sge-integrated",
        }
        return {"remediated": False, "service": service_id, "patch": patch, "mode": "advisory"}


    def _persist_state(self) -> None:
        if self._suspend_persistence or self._state_store is None:
            return
        payload = {
            "baseline_count": self.baseline_count,
            "registry": {service: record.model_dump() for service, record in self.registry.items()},
            "baseline": sorted(self.baseline),
            "route_table": dict(self.route_table),
            "probe_state": self.probe_state,
            "narrative": self.narrative,
            "consolidations": self.consolidations,
        }
        self._state_store.save_json("module-awareness-v1", "state", payload)

    def _restore_persisted_state(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            raise MemoryStoreError("module_awareness_schema_invalid")
        registry_raw = payload.get("registry", {})
        if not isinstance(registry_raw, dict):
            raise MemoryStoreError("module_awareness_schema_invalid")
        try:
            registry = {
                str(service): ModuleRecord.model_validate(record)
                for service, record in registry_raw.items()
            }
            baseline = set(payload.get("baseline", []))
            route_table = dict(payload.get("route_table", DEFAULT_ROUTE_TABLE))
            probe_state = dict(payload.get("probe_state", {}))
            narrative = dict(payload.get("narrative", {}))
            consolidations = dict(payload.get("consolidations", {}))
            baseline_count = int(payload.get("baseline_count", self.baseline_count))
        except (TypeError, ValueError) as exc:
            raise MemoryStoreError("module_awareness_schema_invalid") from exc
        self.registry = registry
        self.baseline = baseline
        self.route_table = route_table
        self.probe_state = probe_state
        self.narrative = narrative
        self.consolidations = consolidations
        self.baseline_count = baseline_count

    def _compliance_check(self, record: ModuleRecord) -> dict[str, Any]:
        violations = []
        if record.ontological_anchor != ONTOLOGICAL_ANCHOR:
            violations.append("ontological_anchor_mismatch")
        if not record.service:
            violations.append("missing_field:service")
        if not record.url:
            violations.append("missing_field:url")
        if not record.registered_at:
            violations.append("missing_field:registered_at")
        if not record.status:
            violations.append("missing_field:status")
        if record.url and "i7iay5r2wq" not in record.url and "667977407542" in record.url:
            violations.append("stale_url_hash")
        if record.url and not record.url.startswith("https://"):
            violations.append("invalid_url_scheme")
        return {"service": record.service, "compliant": not violations, "violations": violations}

    def _entry_id(self, session_id: str, content: str) -> str:
        return hashlib.sha256(f"{session_id}:{content}".encode("utf-8")).hexdigest()[:16]

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
