from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .module_awareness import ModuleAwarenessEngine, ONTOLOGICAL_ANCHOR


VOICE_EVENTS = {"VALIDATE", "ORCHESTRATE", "INTEGRATE", "CERTIFY", "EXECUTE"}
REQUIRED_SEQUENCE = ["VALIDATE", "ORCHESTRATE", "INTEGRATE", "CERTIFY", "EXECUTE"]


class VoiceEventRequest(BaseModel):
    event_type: str
    chain_id: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    prev_signature: str = ""
    sequence: int = 0


class DeploymentGateRequest(BaseModel):
    service: str
    revision: str
    architect_approval: str


class BusSubscribeRequest(BaseModel):
    event_type: str
    subscriber_url: str


class ExecuteGateRequest(BaseModel):
    chain_id: str
    target_service: str
    action: str
    architect_approval: str


class SovereigntySweepRequest(BaseModel):
    module_ids: list[str] = Field(default_factory=list)


class TitanEngine:
    """Integrated SARA-TITAN signed chain, bus and apex authority."""

    def __init__(self, awareness: ModuleAwarenessEngine, secret: str | None = None):
        self.awareness = awareness
        self.secret = secret or os.getenv("TITAN_HMAC_SECRET", ONTOLOGICAL_ANCHOR)
        self.chains: dict[str, list[dict[str, Any]]] = {}
        self.bus_log: dict[str, list[dict[str, Any]]] = {}
        self.subscribers: dict[str, list[str]] = {event: [] for event in VOICE_EVENTS}
        self.deployment_gates: list[dict[str, Any]] = []
        self.execute_gates: list[dict[str, Any]] = []
        self.apex_audits: list[dict[str, Any]] = []

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "sara-titan-integrated",
            "framework": "SARA-TITAN",
            "anchor": ONTOLOGICAL_ANCHOR,
            "capabilities": [
                "voice_event_signing",
                "voice_chain_audit",
                "bus_sequence_verification",
                "deployment_gate",
                "apex_execute_gate",
                "sovereignty_sweep",
                "concentration_governor_context",
                "hawkins_chaos_stability_context",
            ],
            "decision_dynamics": {
                "concentration_governor": "supported_as_objective_lock_context",
                "hawkins_chaos": "supported_as_advisory_stability_context",
                "boundary": "does_not_override_truth_authorization_or_failsafe",
            },
        }

    def emit(self, request: VoiceEventRequest) -> dict[str, Any]:
        chain_id = request.chain_id or str(uuid.uuid4())
        event = self.build_event(
            event_type=request.event_type,
            data=request.data,
            chain_id=chain_id,
            sequence=request.sequence,
            prev_signature=request.prev_signature,
        )
        self.chains.setdefault(chain_id, []).append(event)
        self.chains[chain_id].sort(key=lambda item: int(item.get("sequence", 0)))
        return {
            "emitted": True,
            "event_id": event["event_id"],
            "chain_id": chain_id,
            "sequence": event["sequence"],
            "signature": event["signature"],
            "event": event,
            "anchor": ONTOLOGICAL_ANCHOR,
        }

    def build_event(
        self,
        event_type: str,
        data: dict[str, Any],
        chain_id: str,
        sequence: int,
        prev_signature: str = "",
    ) -> dict[str, Any]:
        event_type = event_type.strip().upper()
        if event_type not in VOICE_EVENTS:
            raise ValueError(f"Invalid VOICE event type: {event_type}")
        event = {
            "event_id": str(uuid.uuid4()),
            "chain_id": chain_id,
            "sequence": sequence,
            "event_type": event_type,
            "data": data,
            "prev_signature": prev_signature,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }
        event["signature"] = self.sign(event)
        return event

    def verify_event(self, event: dict[str, Any]) -> dict[str, Any]:
        signature = str(event.get("signature", ""))
        payload = {k: v for k, v in event.items() if k != "signature"}
        return {
            "valid": self.verify(payload, signature),
            "anchor_ok": event.get("anchor") == ONTOLOGICAL_ANCHOR,
            "event_type_ok": event.get("event_type") in VOICE_EVENTS,
            "anchor": ONTOLOGICAL_ANCHOR,
        }

    def publish(self, event: dict[str, Any]) -> dict[str, Any]:
        verification = self.verify_event(event)
        if not all(verification[k] for k in ("valid", "anchor_ok", "event_type_ok")):
            return {"accepted": False, "reason": "event verification failed", "verification": verification}
        chain_id = str(event["chain_id"])
        seen = self.bus_log.setdefault(chain_id, [])
        expected_sequence = len(seen)
        if int(event["sequence"]) != expected_sequence:
            return {
                "accepted": False,
                "reason": "sequence out of order",
                "expected_sequence": expected_sequence,
                "received_sequence": event["sequence"],
                "anchor": ONTOLOGICAL_ANCHOR,
            }
        seen.append(dict(event))
        event_type = str(event["event_type"])
        return {
            "accepted": True,
            "event_id": event["event_id"],
            "chain_id": chain_id,
            "sequence": event["sequence"],
            "subscribers_notified": len(self.subscribers.get(event_type, [])),
            "anchor": ONTOLOGICAL_ANCHOR,
        }

    def subscribe(self, request: BusSubscribeRequest) -> dict[str, Any]:
        event_type = request.event_type.strip().upper()
        if event_type not in VOICE_EVENTS:
            raise ValueError(f"Invalid event type: {event_type}")
        if request.subscriber_url not in self.subscribers[event_type]:
            self.subscribers[event_type].append(request.subscriber_url)
        return {"subscribed": True, "event_type": event_type, "url": request.subscriber_url, "anchor": ONTOLOGICAL_ANCHOR}

    def sequence_status(self, chain_id: str) -> dict[str, Any]:
        events = self.bus_log.get(chain_id, [])
        return {"chain_id": chain_id, "last_sequence": len(events) - 1, "anchor": ONTOLOGICAL_ANCHOR}

    def deployment_gate(self, request: DeploymentGateRequest) -> dict[str, Any]:
        if request.architect_approval.strip().upper() != "APPROVED":
            return {
                "approved": False,
                "reason": "Deployment blocked. Architect written APPROVED required.",
                "anchor": ONTOLOGICAL_ANCHOR,
            }
        gate_id = str(uuid.uuid4())
        gate = {
            "gate_id": gate_id,
            "service": request.service,
            "revision": request.revision,
            "architect_approval": "APPROVED",
            "gated_at": datetime.now(timezone.utc).isoformat(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }
        self.deployment_gates.append(gate)
        certify = self.emit(
            VoiceEventRequest(
                event_type="CERTIFY",
                chain_id=gate_id,
                sequence=0,
                data={"gate_id": gate_id, "service": request.service, "revision": request.revision},
            )
        )
        return {**gate, "approved": True, "certify_signature": certify["signature"]}

    def audit_chain(self, chain_id: str) -> dict[str, Any]:
        events = self.chains.get(chain_id, [])
        result = self.audit_events(events)
        audit = {
            "audit_id": str(uuid.uuid4()),
            "chain_id": chain_id,
            **result,
            "audited_at": datetime.now(timezone.utc).isoformat(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }
        self.apex_audits.append(audit)
        return audit

    def audit_events(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        ordered = sorted(events, key=lambda item: int(item.get("sequence", 0)))
        violations = []
        prev_sig = ""
        event_types_seen = []
        for index, event in enumerate(ordered):
            verification = self.verify_event(event)
            if not verification["valid"]:
                violations.append(f"seq {event.get('sequence', index)}: HMAC signature invalid")
            if not verification["anchor_ok"]:
                violations.append(f"seq {event.get('sequence', index)}: anchor mismatch")
            if event.get("prev_signature") != prev_sig:
                violations.append(f"seq {event.get('sequence', index)}: prev_signature chain broken")
            if event.get("sequence") != index:
                violations.append(f"expected sequence {index}, got {event.get('sequence')}")
            prev_sig = str(event.get("signature", ""))
            event_types_seen.append(event.get("event_type"))
        for required in REQUIRED_SEQUENCE:
            if required not in event_types_seen:
                violations.append(f"missing required VOICE event: {required}")
        return {
            "event_count": len(ordered),
            "event_types": event_types_seen,
            "violations": violations,
            "chain_valid": not violations,
        }

    def execute_gate(self, request: ExecuteGateRequest) -> dict[str, Any]:
        if request.architect_approval.strip().upper() != "APPROVED":
            return {
                "execute_authorized": False,
                "reason": "EXECUTE blocked: Architect written APPROVED required.",
                "anchor": ONTOLOGICAL_ANCHOR,
            }
        audit = self.audit_chain(request.chain_id)
        if not audit["chain_valid"]:
            return {
                "execute_authorized": False,
                "reason": "EXECUTE blocked: chain integrity violations.",
                "violations": audit["violations"],
                "anchor": ONTOLOGICAL_ANCHOR,
            }
        gate = {
            "gate_id": str(uuid.uuid4()),
            "chain_id": request.chain_id,
            "target_service": request.target_service,
            "action": request.action,
            "architect_approval": "APPROVED",
            "chain_valid": True,
            "gated_at": datetime.now(timezone.utc).isoformat(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }
        self.execute_gates.append(gate)
        return {**gate, "execute_authorized": True, "chain_event_count": audit["event_count"]}

    def sovereignty_sweep(self, request: SovereigntySweepRequest) -> dict[str, Any]:
        audit = self.awareness.audit()
        violations = audit["violations"]
        if request.module_ids:
            wanted = set(request.module_ids)
            violations = [v for v in violations if v["service"] in wanted]
            swept = len(request.module_ids)
        else:
            swept = audit["total_audited"]
        return {
            "sweep_id": str(uuid.uuid4()),
            "modules_swept": swept,
            "violation_count": len(violations),
            "violations": violations,
            "sovereign": len(violations) == 0,
            "swept_at": datetime.now(timezone.utc).isoformat(),
            "anchor": ONTOLOGICAL_ANCHOR,
        }

    def sign(self, payload: dict[str, Any]) -> str:
        clean = {k: v for k, v in payload.items() if k != "signature"}
        msg = json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hmac.new(self.secret.encode("utf-8"), msg, hashlib.sha3_512).hexdigest()

    def verify(self, payload: dict[str, Any], signature: str) -> bool:
        return hmac.compare_digest(self.sign(payload), signature)
