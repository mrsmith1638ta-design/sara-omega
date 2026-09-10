from __future__ import annotations

import ast
import builtins
import hashlib
import io
import re
import tokenize
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, Field


MadhouseDecision = Literal["BLOCKED", "READY_FOR_VERIFICATION"]


class MadhouseReviewRequest(BaseModel):
    candidate_id: str = Field(default="candidate", max_length=256)
    language: str = Field(default="python", max_length=64)
    generated_code: str = ""
    requirements: list[str] = Field(default_factory=list)
    previous_failures: list[dict[str, Any]] = Field(default_factory=list)
    recurring_failure_threshold: int = Field(default=2, ge=1, le=10)
    context: dict[str, Any] = Field(default_factory=dict)


class MadhouseAgent:
    """Adversarial critique and code-quality gate for SARA.

    Madhouse can demonstrate and block defects. It cannot promote code to PASS,
    certify production readiness, or override SIOS/ROAD/SARA decisions.
    """

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "sara-madhouse-agent",
            "role": "adversarial_critique_and_code_quality_gate",
            "can_block": True,
            "can_pass": False,
            "promotion_authority": "NONE",
            "modes": [
                "syntax_destroyer",
                "broken_code_detector",
                "repeatability_critic",
                "duplication_hunter",
                "logic_attacker",
                "security_critic",
                "quality_critic",
                "assumption_killer",
                "contrarian",
                "black_swan",
                "mutation_engine",
                "second_order_critic",
            ],
            "boundary": "may_block_candidates; never certifies production PASS",
        }

    def review(self, request: MadhouseReviewRequest) -> dict[str, Any]:
        findings = self._findings(request)
        findings.extend(self._recurring_findings(request, findings))
        blocking = [item for item in findings if item["severity"] in {"BLOCKING", "CRITICAL"}]
        decision: MadhouseDecision = "BLOCKED" if blocking else "READY_FOR_VERIFICATION"

        return {
            "service": "sara-madhouse-agent",
            "candidate_id": request.candidate_id,
            "decision": decision,
            "can_block": True,
            "can_pass": False,
            "promotion_authority": "NONE",
            "execution_authority": "NONE",
            "findings": findings,
            "evidence_ledger": self._evidence_ledger(request.candidate_id, findings),
            "failure_fingerprints": [item["fingerprint"] for item in findings],
            "required_actions": self._required_actions(decision, findings),
            "required_validation": [
                "compile",
                "static_analysis",
                "unit_tests",
                "integration_tests",
                "security_review",
            ],
            "boundary": "Madhouse absence of findings is not proof of correctness; send survivors to Verification/ROAD/SIOS.",
        }

    def _findings(self, request: MadhouseReviewRequest) -> list[dict[str, Any]]:
        code = request.generated_code or ""
        language = request.language.lower().strip()
        findings: list[dict[str, Any]] = []
        if not code.strip():
            return [
                self._finding(
                    "EMPTY_CANDIDATE",
                    "BLOCKING",
                    "No generated code was supplied for critique.",
                    reproducible=True,
                )
            ]

        if language in {"py", "python"}:
            tree = None
            try:
                tree = ast.parse(code)
            except SyntaxError as exc:
                findings.append(
                    self._finding(
                        "SYNTAX",
                        "BLOCKING",
                        f"Python parser failure at line {exc.lineno or 'unknown'}: {exc.msg}",
                        reproducible=True,
                        line=exc.lineno,
                    )
                )
            if tree is not None:
                findings.extend(self._python_static_findings(tree, code))

        findings.extend(self._duplication_findings(code))
        findings.extend(self._security_findings(code))
        findings.extend(self._quality_findings(code))
        return findings

    def _python_static_findings(self, tree: ast.AST, code: str) -> list[dict[str, Any]]:
        defined = set(dir(builtins)) | {"True", "False", "None", "__name__"}
        used: list[tuple[str, int | None]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                defined.add(node.name)
            elif isinstance(node, ast.arg):
                defined.add(node.arg)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, (ast.Store, ast.Param)):
                    defined.add(node.id)
                elif isinstance(node.ctx, ast.Load):
                    used.append((node.id, getattr(node, "lineno", None)))
            elif isinstance(node, ast.alias):
                defined.add((node.asname or node.name.split(".")[0]))
            elif isinstance(node, ast.ExceptHandler) and node.name:
                defined.add(str(node.name))

        findings = []
        for name, line in sorted(set(used)):
            if name not in defined:
                findings.append(
                    self._finding(
                        "UNDEFINED_SYMBOL",
                        "BLOCKING",
                        f"Name `{name}` is read before any local definition, import, or known builtin.",
                        reproducible=True,
                        line=line,
                        token=name,
                    )
                )

        for node in ast.walk(tree):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) and node.value.value is True:
                surrounding = self._line_window(code, getattr(node, "lineno", 0), radius=3).lower()
                if re.search(r"except|error|fail|failure", surrounding):
                    findings.append(
                        self._finding(
                            "LOGIC",
                            "BLOCKING",
                            "Failure/error branch appears to return success=True.",
                            reproducible=True,
                            line=getattr(node, "lineno", None),
                        )
                    )
        return findings

    def _duplication_findings(self, code: str) -> list[dict[str, Any]]:
        logical_lines = [
            line.strip()
            for line in code.splitlines()
            if line.strip() and not line.strip().startswith("#") and len(line.strip()) >= 12
        ]
        counts = Counter(logical_lines)
        duplicate_lines = [line for line, count in counts.items() if count >= 3]
        if not duplicate_lines:
            return []
        return [
            self._finding(
                "DUPLICATION",
                "HIGH",
                f"{len(duplicate_lines)} repeated code line pattern(s) appear at least 3 times.",
                reproducible=True,
                token=self._short_hash("|".join(duplicate_lines)),
            )
        ]

    def _security_findings(self, code: str) -> list[dict[str, Any]]:
        findings = []
        lowered = code.lower()
        risky_calls = ["eval(", "exec(", "subprocess.call(", "shell=true"]
        for marker in risky_calls:
            if marker in lowered:
                findings.append(
                    self._finding(
                        "SECURITY",
                        "BLOCKING",
                        f"Risky execution marker `{marker}` requires security review before promotion.",
                        reproducible=True,
                        token=marker,
                    )
                )
        if re.search(r"(api[_-]?key|secret|token)\s*=\s*['\"][^'\"]{12,}", code, re.IGNORECASE):
            findings.append(
                self._finding(
                    "SECRET_EXPOSURE",
                    "BLOCKING",
                    "Code appears to contain a hard-coded credential-like value.",
                    reproducible=True,
                )
            )
        return findings

    def _quality_findings(self, code: str) -> list[dict[str, Any]]:
        try:
            token_count = sum(1 for _ in tokenize.generate_tokens(io.StringIO(code).readline))
        except tokenize.TokenError:
            return []
        line_count = max(1, len([line for line in code.splitlines() if line.strip()]))
        if token_count / line_count > 24:
            return [
                self._finding(
                    "QUALITY",
                    "MEDIUM",
                    "Candidate has unusually dense statements; maintainability review is required.",
                    reproducible=False,
                )
            ]
        return []

    def _recurring_findings(
        self,
        request: MadhouseReviewRequest,
        current_findings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        previous = Counter(str(item.get("fingerprint", "")) for item in request.previous_failures)
        recurring = []
        for finding in current_findings:
            fingerprint = finding["fingerprint"]
            repeat_count = previous.get(fingerprint, 0) + 1
            if repeat_count > request.recurring_failure_threshold:
                recurring.append(
                    self._finding(
                        "RECURRING_FAILURE",
                        "CRITICAL",
                        f"Failure fingerprint `{fingerprint}` has survived {repeat_count} candidate attempts.",
                        reproducible=True,
                        token=fingerprint,
                        repeat_count=repeat_count,
                    )
                )
        return recurring

    def _evidence_ledger(self, candidate_id: str, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "candidate_id": candidate_id,
                "issue": finding["class"],
                "severity": finding["severity"],
                "reproduced": finding["reproducible"],
                "fixed": False,
                "retested": False,
                "evidence": finding["evidence"],
                "state": "VERIFIED" if finding["reproducible"] else "SUPPORTED",
                "fingerprint": finding["fingerprint"],
            }
            for finding in findings
        ]

    def _required_actions(self, decision: MadhouseDecision, findings: list[dict[str, Any]]) -> list[str]:
        if decision != "BLOCKED":
            return ["Send candidate to Verification Agent; Madhouse cannot grant PASS."]
        actions = []
        if any(item["class"] == "RECURRING_FAILURE" for item in findings):
            actions.append("Discard the current repair strategy and isolate the root assumption.")
        if any(item["class"] == "SYNTAX" for item in findings):
            actions.append("Repair syntax until the candidate parses cleanly.")
        if any(item["class"] == "UNDEFINED_SYMBOL" for item in findings):
            actions.append("Define, import, or remove unresolved symbols with a structurally valid fix.")
        if any(item["class"] == "LOGIC" for item in findings):
            actions.append("Repair failure-state logic and add targeted regression coverage.")
        if any(item["class"] in {"SECURITY", "SECRET_EXPOSURE"} for item in findings):
            actions.append("Remove unsafe execution or credential exposure before retest.")
        actions.append("Return the repaired candidate to Madhouse for adversarial retest.")
        return actions

    def _finding(
        self,
        klass: str,
        severity: str,
        evidence: str,
        *,
        reproducible: bool,
        line: int | None = None,
        token: str | None = None,
        repeat_count: int | None = None,
    ) -> dict[str, Any]:
        fingerprint = f"{klass}:{token or self._short_hash(evidence)}"
        out = {
            "class": klass,
            "severity": severity,
            "evidence": evidence,
            "reproducible": reproducible,
            "state": "VERIFIED" if reproducible else "SUPPORTED",
            "fingerprint": fingerprint,
        }
        if line is not None:
            out["line"] = line
        if repeat_count is not None:
            out["repeat_count"] = repeat_count
        return out

    def _line_window(self, code: str, line: int, *, radius: int) -> str:
        lines = code.splitlines()
        start = max(0, line - radius - 1)
        end = min(len(lines), line + radius)
        return "\n".join(lines[start:end])

    def _short_hash(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
