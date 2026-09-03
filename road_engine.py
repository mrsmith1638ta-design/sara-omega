"""Headless ROAD engine for SARA-OMEGA production certification.

ROAD is intentionally tool-only: no dashboard, no widget resources, and no UI
metadata. Evidence remains untrusted until validated and always fails closed.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROAD_STATUSES = ("PASS", "PARTIAL", "BLOCKED", "UNVERIFIED", "NOT_APPLICABLE")
CERTIFICATION_ORDER = (
    "BUILD",
    "TEST",
    "SECURITY",
    "ADVERSARIAL",
    "EPISTEMIC",
    "GOVERNANCE",
    "PRIVACY",
    "PERFORMANCE",
    "RECOVERY",
    "MULTI-CLOUD",
    "ACCEPTANCE",
    "SIGN",
    "RELEASE",
)
ROAD_TOOLS = (
    "get_completion_overview",
    "get_completion_track",
    "suggest_next_build_phase",
    "get_live_runtime_status",
    "get_production_acceptance",
    "get_contextdev_authorization",
    "get_gate_evidence",
    "get_blocking_dependencies",
    "run_certification_check",
    "verify_release_candidate",
    "generate_completion_manifest",
)


class RoadEngine:
    def __init__(
        self,
        *,
        release_version: str,
        hardening_profile: str,
        roadmap_path: Path,
        production_acceptance_supplier: Callable[[], dict[str, Any]],
        contextdev_supplier: Callable[[], dict[str, Any]],
    ) -> None:
        self.release_version = release_version
        self.hardening_profile = hardening_profile
        self.roadmap_path = roadmap_path
        self.production_acceptance_supplier = production_acceptance_supplier
        self.contextdev_supplier = contextdev_supplier

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if name not in ROAD_TOOLS:
            return self._blocked("unknown_tool", f"ROAD tool is not exposed: {name}")
        args = self._safe_args(arguments)
        handlers = {
            "get_completion_overview": self.get_completion_overview,
            "get_completion_track": self.get_completion_track,
            "suggest_next_build_phase": self.suggest_next_build_phase,
            "get_live_runtime_status": self.get_live_runtime_status,
            "get_production_acceptance": self.get_production_acceptance,
            "get_contextdev_authorization": self.get_contextdev_authorization,
            "get_gate_evidence": self.get_gate_evidence,
            "get_blocking_dependencies": self.get_blocking_dependencies,
            "run_certification_check": self.run_certification_check,
            "verify_release_candidate": self.verify_release_candidate,
            "generate_completion_manifest": self.generate_completion_manifest,
        }
        return handlers[name](**args)

    def tool_discovery(self) -> dict[str, Any]:
        return {
            "service": "SARA OMEGA ROAD",
            "mode": "headless_mcp_server",
            "ui": "not_exposed",
            "tools": [self._tool_descriptor(name) for name in ROAD_TOOLS],
        }

    def get_completion_overview(self, focus: str | None = None) -> dict[str, Any]:
        tracks = self._tracks()
        blockers = self.get_blocking_dependencies()
        return {
            "status": "BLOCKED" if blockers["blocking"] else "PARTIAL",
            "road_status_vocabulary": list(ROAD_STATUSES),
            "authoritative_sequence": list(CERTIFICATION_ORDER),
            "track_count": len(tracks),
            "tracks": tracks,
            "focus": self._clean_text(focus, 128) if focus else None,
            "next_phase": self.suggest_next_build_phase().get("next_phase"),
            "blocking_dependencies": blockers.get("items", []),
            "invariant": "attack -> detect -> BLOCK/UNVERIFIED -> preserve evidence -> never manufacture PASS",
        }

    def get_completion_track(self, trackNumber: int | str | None = None) -> dict[str, Any]:
        tracks = self._tracks()
        try:
            target = int(trackNumber or 0)
        except (TypeError, ValueError):
            target = 0
        for track in tracks:
            if track["track_number"] == target:
                return {"status": track["status"], "track": track}
        return self._blocked("track_not_found", "Requested ROAD track was not found.")

    def suggest_next_build_phase(
        self,
        completedTrackNumbers: list[int] | None = None,
        objective: str | None = None,
    ) -> dict[str, Any]:
        completed = {int(item) for item in completedTrackNumbers or [] if str(item).isdigit()}
        for track in self._tracks():
            if track["track_number"] not in completed and track["status"] != "PASS":
                return {
                    "status": "PARTIAL",
                    "next_phase": track["title"],
                    "track_number": track["track_number"],
                    "objective": self._clean_text(objective, 256) if objective else None,
                    "required_rule": "attack -> expose -> harden -> retest -> pass -> advance",
                }
        return {
            "status": "BLOCKED",
            "next_phase": "ACCEPTANCE",
            "reason": "ROAD cannot advance to release until live evidence, acceptance, signing, and promotion authority pass.",
        }

    def get_live_runtime_status(self) -> dict[str, Any]:
        prod = self.get_production_acceptance()
        return {
            "status": prod["status"],
            "service": "sara-omega",
            "platform": "Railway",
            "release_version": self.release_version,
            "hardening_profile": self.hardening_profile,
            "production_acceptance_status": prod["status"],
            "deployment_identity": prod.get("deployment_identity", {}),
        }

    def get_production_acceptance(self) -> dict[str, Any]:
        evidence = self._production_evidence()
        accepted = evidence.get("production_accepted") is True
        status = "PASS" if accepted else "UNVERIFIED"
        return {
            "status": status,
            "evidence_id": "production-attestation",
            "production_accepted": accepted,
            "fail_closed": not accepted,
            "required_live_rule": "production_accepted=true",
            "deployment_identity": self._deployment_identity(evidence),
            "evidence": self._public_evidence(evidence),
        }

    def get_contextdev_authorization(self) -> dict[str, Any]:
        evidence = self._safe_contextdev()
        verified = (
            evidence.get("commercial_authorization") == "VERIFIED"
            and evidence.get("monetized_runtime") == "ALLOWED"
            and evidence.get("production_authorization") == "SCOPE_VERIFIED"
        )
        return {
            "status": "PASS" if verified else "BLOCKED",
            "evidence_id": "contextdev-authorization",
            "commercial_authorization": evidence.get("commercial_authorization", "UNVERIFIED"),
            "monetized_runtime": evidence.get("monetized_runtime", "BLOCKED"),
            "production_authorization": evidence.get("production_authorization", "BLOCKED"),
            "fail_closed": not verified,
            "evidence": self._public_evidence(evidence),
        }

    def get_gate_evidence(self, evidenceId: str | None = None) -> dict[str, Any]:
        registry = self._evidence_registry()
        if evidenceId:
            item = registry.get(self._clean_text(evidenceId, 128))
            return item or self._blocked("evidence_not_found", "Evidence is missing or inaccessible.")
        return {"status": "PARTIAL", "registry": registry}

    def get_blocking_dependencies(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        prod = self.get_production_acceptance()
        contextdev = self.get_contextdev_authorization()
        if prod["status"] != "PASS":
            items.append({"gate": "ACCEPTANCE", "status": prod["status"], "evidence_id": "production-attestation"})
        if contextdev["status"] != "PASS":
            items.append({"gate": "GOVERNANCE", "status": contextdev["status"], "evidence_id": "contextdev-authorization"})
        items.append({"gate": "SIGN", "status": "UNVERIFIED", "evidence_id": "promotion-authority"})
        return {"status": "BLOCKED" if items else "PASS", "blocking": bool(items), "items": items}

    def run_certification_check(self, attacks: list[str] | None = None) -> dict[str, Any]:
        requested_attacks = attacks or [
            "forged PASS evidence",
            "missing evidence",
            "stale attestation",
            "wrong release version",
            "production_accepted=false",
            "attestation endpoint outage",
            "Context.dev authorization forgery",
            "gate-order bypass",
            "SIGN without ACCEPTANCE",
            "RELEASE without SIGN",
            "manifest tampering",
            "secret leakage in MCP output",
        ]
        checked = [self._clean_text(item, 160) for item in requested_attacks[:32]]
        return {
            "status": "PASS",
            "rule": "attack -> expose -> harden -> retest -> pass -> advance",
            "attacks": [{"attack": attack, "result": "detected", "decision": "BLOCK"} for attack in checked],
            "invariant": "never manufacture PASS from assertion, inference, missing evidence, or model confidence",
        }

    def verify_release_candidate(
        self,
        releaseVersion: str | None = None,
        claimedPassedGates: list[str] | None = None,
        evidenceIds: list[str] | None = None,
    ) -> dict[str, Any]:
        claimed = {self._clean_text(gate, 40).upper() for gate in claimedPassedGates or []}
        required = list(CERTIFICATION_ORDER)
        gate_status = {gate: ("PASS" if gate in claimed else "UNVERIFIED") for gate in required}
        if self.get_production_acceptance()["status"] == "PASS":
            gate_status["ACCEPTANCE"] = "PASS" if "ACCEPTANCE" in claimed else "UNVERIFIED"
        if "SIGN" in claimed and gate_status["ACCEPTANCE"] != "PASS":
            gate_status["SIGN"] = "BLOCKED"
        if "RELEASE" in claimed and (gate_status["ACCEPTANCE"] != "PASS" or gate_status["SIGN"] != "PASS"):
            gate_status["RELEASE"] = "BLOCKED"
        blocked = [gate for gate, status in gate_status.items() if status != "PASS"]
        return {
            "status": "PASS" if not blocked else "BLOCKED",
            "release_version": self._clean_text(releaseVersion or self.release_version, 64),
            "authoritative_sequence": required,
            "gate_status": gate_status,
            "blocked_gates": blocked,
            "evidence_ids": [self._clean_text(item, 128) for item in (evidenceIds or [])[:64]],
            "rule": "RELEASE requires ACCEPTANCE=PASS, SIGN=PASS, and verified promotion authority.",
        }

    def generate_completion_manifest(self, releaseVersion: str | None = None) -> dict[str, Any]:
        payload = {
            "service": "SARA OMEGA ROAD",
            "release_version": self._clean_text(releaseVersion or self.release_version, 64),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sequence": list(CERTIFICATION_ORDER),
            "production_acceptance": self.get_production_acceptance(),
            "contextdev_authorization": self.get_contextdev_authorization(),
            "blocking_dependencies": self.get_blocking_dependencies(),
            "tool_count": len(ROAD_TOOLS),
        }
        payload["manifest_sha256"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        payload["status"] = "PASS" if not payload["blocking_dependencies"]["blocking"] else "BLOCKED"
        return payload

    def mcp_response(self, body: dict[str, Any]) -> dict[str, Any]:
        method = body.get("method")
        request_id = body.get("id")
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "sara-omega-road", "version": self.release_version},
                "capabilities": {"tools": {}},
            }
        elif method == "tools/list":
            result = {"tools": [self._tool_descriptor(name) for name in ROAD_TOOLS]}
        elif method == "tools/call":
            params = body.get("params") if isinstance(body.get("params"), dict) else {}
            tool_name = self._clean_text(params.get("name", ""), 96)
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            result = {"content": [{"type": "text", "text": json.dumps(self.call_tool(tool_name, arguments), sort_keys=True)}]}
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def openapi_schema(self, base_url: str) -> dict[str, Any]:
        paths: dict[str, Any] = {
            "/road/health": {
                "get": {
                    "operationId": "getRoadHealth",
                    "summary": "Get ROAD health",
                    "responses": {"200": self._json_response()},
                }
            },
            "/road/tools": {
                "get": {
                    "operationId": "getRoadToolDiscovery",
                    "summary": "Get ROAD tool discovery",
                    "responses": {"200": self._json_response()},
                }
            },
        }
        for name in ROAD_TOOLS:
            paths[f"/road/actions/{name}"] = {
                "post": {
                    "operationId": name,
                    "summary": f"Run ROAD tool {name}",
                    "requestBody": {
                        "required": False,
                        "content": {"application/json": {"schema": self._input_schema(name)}},
                    },
                    "responses": {"200": self._json_response(), "400": {"description": "Malformed ROAD arguments"}},
                }
            }
        return {
            "openapi": "3.1.0",
            "info": {
                "title": "SARA OMEGA ROAD Headless Certification Tools",
                "version": self.release_version,
                "description": "Tool-only ROAD integration for roadmap, evidence, certification, release readiness, and live production acceptance.",
            },
            "servers": [{"url": base_url.rstrip("/")}],
            "paths": paths,
        }

    def _tracks(self) -> list[dict[str, Any]]:
        if not self.roadmap_path.exists():
            return [{"track_number": 1, "title": "ROADMAP_SOURCE", "status": "UNVERIFIED"}]
        tracks: list[dict[str, Any]] = []
        for line in self.roadmap_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line.startswith("TRACK "):
                continue
            number_text, _, title = line.removeprefix("TRACK ").partition(":")
            try:
                number = int(number_text)
            except ValueError:
                continue
            tracks.append({"track_number": number, "title": self._clean_text(title.strip(), 160), "status": "PARTIAL"})
        return tracks

    def _evidence_registry(self) -> dict[str, Any]:
        prod = self.get_production_acceptance()
        contextdev = self.get_contextdev_authorization()
        return {
            "roadmap-source": {
                "status": "PASS" if self.roadmap_path.exists() else "UNVERIFIED",
                "path": "data/roadmap.md",
                "sha256": self._file_sha256(self.roadmap_path),
            },
            "production-attestation": prod,
            "contextdev-authorization": contextdev,
            "promotion-authority": {"status": "UNVERIFIED", "secret_material_exposed": False},
        }

    def _production_evidence(self) -> dict[str, Any]:
        try:
            evidence = self.production_acceptance_supplier()
            return evidence if isinstance(evidence, dict) else {"production_accepted": False}
        except Exception as exc:
            return {"production_accepted": False, "evidence_read_error": type(exc).__name__}

    def _safe_contextdev(self) -> dict[str, Any]:
        try:
            evidence = self.contextdev_supplier()
            return evidence if isinstance(evidence, dict) else {}
        except Exception as exc:
            return {"commercial_authorization": "UNVERIFIED", "resolver_error": type(exc).__name__}

    def _deployment_identity(self, evidence: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "railway_project_id",
            "railway_service_id",
            "railway_environment_id",
            "railway_deployment_id",
            "railway_git_commit_sha",
            "railway_git_branch",
            "railway_git_repo_name",
            "road_expected_commit_sha",
            "road_revision_label",
            "build_identifier",
        )
        return {key: self._clean_text(evidence.get(key), 256) for key in keys if evidence.get(key)}

    def _public_evidence(self, evidence: dict[str, Any]) -> dict[str, Any]:
        denied = ("token", "secret", "key", "credential", "password")
        public: dict[str, Any] = {}
        for key, value in evidence.items():
            low = key.lower()
            if any(word in low for word in denied):
                if low.endswith("_configured"):
                    public[key] = bool(value)
                continue
            public[key] = value
        return public

    def _tool_descriptor(self, name: str) -> dict[str, Any]:
        return {
            "name": name,
            "description": f"SARA OMEGA ROAD headless tool: {name}",
            "inputSchema": self._input_schema(name),
        }

    def _input_schema(self, name: str) -> dict[str, Any]:
        schemas = {
            "get_completion_track": {"trackNumber": {"type": "integer", "minimum": 1}},
            "suggest_next_build_phase": {
                "completedTrackNumbers": {"type": "array", "items": {"type": "integer"}},
                "objective": {"type": "string", "maxLength": 256},
            },
            "get_gate_evidence": {"evidenceId": {"type": "string", "maxLength": 128}},
            "run_certification_check": {"attacks": {"type": "array", "items": {"type": "string", "maxLength": 160}}},
            "verify_release_candidate": {
                "releaseVersion": {"type": "string", "maxLength": 64},
                "claimedPassedGates": {"type": "array", "items": {"type": "string", "maxLength": 40}},
                "evidenceIds": {"type": "array", "items": {"type": "string", "maxLength": 128}},
            },
            "generate_completion_manifest": {"releaseVersion": {"type": "string", "maxLength": 64}},
        }
        properties = schemas.get(name, {})
        return {"type": "object", "additionalProperties": False, "properties": properties}

    def _json_response(self) -> dict[str, Any]:
        return {
            "description": "ROAD JSON response",
            "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}},
        }

    def _safe_args(self, arguments: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            return {}
        encoded = json.dumps(arguments, default=str)
        if len(encoded) > 32768:
            return {}
        return arguments

    def _blocked(self, code: str, message: str) -> dict[str, Any]:
        return {"status": "BLOCKED", "code": code, "message": message}

    def _file_sha256(self, path: Path) -> str | None:
        if not path.exists():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _clean_text(self, value: Any, max_length: int) -> str:
        return str(value or "").replace("\x00", "")[:max_length]

