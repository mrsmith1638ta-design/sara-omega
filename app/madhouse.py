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
                        evidence_state="VERIFIED",
                        family_fingerprint="SYNTAX:parser-failure",
                    )
                )
            if tree is not None:
                findings.extend(self._python_static_findings(tree, code))
                findings.extend(self._python_structural_duplication_findings(tree))

        findings.extend(self._duplication_findings(code))
        findings.extend(self._security_findings(code))
        findings.extend(self._quality_findings(code))
        return findings

    def _python_static_findings(self, tree: ast.AST, code: str) -> list[dict[str, Any]]:
        findings = self._undefined_symbol_findings(tree)
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
                            evidence_state="SUPPORTED",
                            family_fingerprint="LOGIC:success-return-in-failure-context",
                        )
                    )
        return findings

    def _undefined_symbol_findings(self, tree: ast.AST) -> list[dict[str, Any]]:
        defined = set(dir(builtins)) | {"True", "False", "None", "__name__"}
        findings: list[dict[str, Any]] = []
        seen: set[tuple[str, int | None]] = set()

        def direct_stores(statement: ast.stmt) -> set[str]:
            targets: list[ast.AST] = []
            if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                if isinstance(statement, ast.Assign):
                    targets.extend(statement.targets)
                else:
                    targets.append(statement.target)
            elif isinstance(statement, (ast.For, ast.AsyncFor)):
                targets.append(statement.target)
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                targets.extend(item.optional_vars for item in statement.items if item.optional_vars)
            elif isinstance(statement, ast.NamedExpr):
                targets.append(statement.target)
            stores: set[str] = set()
            for target in targets:
                stores.update(name for name, _line in self._stores(target))
            return stores

        def report_loads(statement: ast.AST, scope_defined: set[str]) -> None:
            for name, line in self._loads(statement):
                if name not in scope_defined and (name, line) not in seen:
                    seen.add((name, line))
                    findings.append(
                        self._finding(
                            "UNDEFINED_SYMBOL",
                            "BLOCKING",
                            f"Name `{name}` is read before any local definition, import, or known builtin.",
                            reproducible=False,
                            line=line,
                            token=name,
                            evidence_state="SUPPORTED",
                            family_fingerprint="UNDEFINED_SYMBOL:read-before-definition",
                        )
                    )

        def analyze_body(statements: list[ast.stmt], scope_defined: set[str]) -> None:
            for statement in statements:
                if isinstance(statement, (ast.Import, ast.ImportFrom)):
                    scope_defined.update(self._import_names(statement))
                    continue
                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    scope_defined.add(statement.name)
                    function_defined = set(dir(builtins)) | {arg.arg for arg in statement.args.args}
                    function_defined.update(arg.arg for arg in statement.args.posonlyargs)
                    function_defined.update(arg.arg for arg in statement.args.kwonlyargs)
                    if statement.args.vararg:
                        function_defined.add(statement.args.vararg.arg)
                    if statement.args.kwarg:
                        function_defined.add(statement.args.kwarg.arg)
                    analyze_body(statement.body, function_defined | scope_defined)
                    continue
                if isinstance(statement, ast.ClassDef):
                    scope_defined.add(statement.name)
                    analyze_body(statement.body, set(dir(builtins)) | scope_defined)
                    continue
                if isinstance(statement, ast.ExceptHandler) and statement.name:
                    scope_defined.add(str(statement.name))

                if isinstance(statement, (ast.For, ast.AsyncFor)):
                    report_loads(statement.iter, scope_defined)
                    loop_scope = set(scope_defined) | direct_stores(statement)
                    analyze_body(statement.body, loop_scope)
                    analyze_body(statement.orelse, set(scope_defined))
                    continue
                if isinstance(statement, ast.If):
                    report_loads(statement.test, scope_defined)
                    body_scope = set(scope_defined)
                    else_scope = set(scope_defined)
                    analyze_body(statement.body, body_scope)
                    analyze_body(statement.orelse, else_scope)
                    scope_defined.update(body_scope & else_scope)
                    continue
                report_loads(statement, scope_defined)
                scope_defined.update(direct_stores(statement))

        module_scope = set(defined)
        module_scope.update(
            statement.name
            for statement in getattr(tree, "body", [])
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        )
        analyze_body(list(getattr(tree, "body", [])), module_scope)
        return findings

    def _loads(self, node: ast.AST) -> list[tuple[str, int | None]]:
        comprehension_bound: set[str] = set()
        loop_bound: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.comprehension):
                loop_bound.update(name for name, _line in self._stores(child.target))
            elif isinstance(child, (ast.For, ast.AsyncFor)):
                loop_bound.update(name for name, _line in self._stores(child.target))
        bound = comprehension_bound | loop_bound
        return [
            (child.id, getattr(child, "lineno", None))
            for child in ast.walk(node)
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and child.id not in bound
        ]

    def _stores(self, node: ast.AST) -> list[tuple[str, int | None]]:
        stores = []
        comprehension_bound: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.comprehension):
                comprehension_bound.update(name for name, _line in self._stores(child.target))
        for child in ast.walk(node):
            if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Param)):
                if child.id not in comprehension_bound:
                    stores.append((child.id, getattr(child, "lineno", None)))
            elif isinstance(child, ast.ExceptHandler) and child.name:
                stores.append((str(child.name), getattr(child, "lineno", None)))
        return stores

    def _import_names(self, node: ast.Import | ast.ImportFrom) -> set[str]:
        return {alias.asname or alias.name.split(".")[0] for alias in node.names}

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
                reproducible=False,
                token=self._short_hash("|".join(duplicate_lines)),
                evidence_state="SUPPORTED",
                family_fingerprint="DUPLICATION:repeated-logical-lines",
            )
        ]

    def _python_structural_duplication_findings(self, tree: ast.AST) -> list[dict[str, Any]]:
        patterns = [
            self._normalized_ast(statement)
            for statement in getattr(tree, "body", [])
            if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Expr, ast.Return, ast.If, ast.For))
        ]
        counts = Counter(pattern for pattern in patterns if pattern)
        duplicated = [pattern for pattern, count in counts.items() if count >= 3]
        if not duplicated:
            return []
        return [
            self._finding(
                "DUPLICATION",
                "HIGH",
                f"{len(duplicated)} structurally similar AST statement pattern(s) appear at least 3 times.",
                reproducible=False,
                token=self._short_hash("|".join(duplicated)),
                evidence_state="SUPPORTED",
                family_fingerprint="DUPLICATION:normalized-ast-statement",
            )
        ]

    def _normalized_ast(self, node: ast.AST) -> str:
        class Normalizer(ast.NodeTransformer):
            def visit_Name(self, child: ast.Name) -> ast.AST:
                return ast.copy_location(ast.Name(id="NAME", ctx=child.ctx), child)

            def visit_arg(self, child: ast.arg) -> ast.arg:
                return ast.copy_location(ast.arg(arg="ARG", annotation=None, type_comment=None), child)

            def visit_Constant(self, child: ast.Constant) -> ast.AST:
                return ast.copy_location(ast.Constant(value="CONST"), child)

            def visit_Attribute(self, child: ast.Attribute) -> ast.AST:
                self.generic_visit(child)
                child.attr = "ATTR"
                return child

        normalized = Normalizer().visit(ast.fix_missing_locations(ast.copy_location(node, node)))
        return ast.dump(normalized, include_attributes=False)

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
                        reproducible=False,
                        token=marker,
                        evidence_state="SUPPORTED",
                        family_fingerprint=f"SECURITY:{marker}",
                    )
                )
        if re.search(r"(api[_-]?key|secret|token)\s*=\s*['\"][^'\"]{12,}", code, re.IGNORECASE):
            findings.append(
                self._finding(
                    "SECRET_EXPOSURE",
                    "BLOCKING",
                    "Code appears to contain a hard-coded credential-like value.",
                    reproducible=False,
                    evidence_state="SUPPORTED",
                    family_fingerprint="SECRET_EXPOSURE:credential-like-literal",
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
                    evidence_state="SUPPORTED",
                    family_fingerprint="QUALITY:dense-statements",
                )
            ]
        return []

    def _recurring_findings(
        self,
        request: MadhouseReviewRequest,
        current_findings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        previous = Counter()
        for item in request.previous_failures:
            recorded = False
            for key in ("fingerprint", "family_fingerprint"):
                if item.get(key):
                    previous[str(item[key])] += 1
                    recorded = True
            if not recorded and item.get("class"):
                previous[f"{item['class']}:read-before-definition"] += 1
        recurring = []
        for finding in current_findings:
            fingerprint = finding["fingerprint"]
            family = finding["family_fingerprint"]
            repeat_count = max(previous.get(fingerprint, 0), previous.get(family, 0)) + 1
            if repeat_count > request.recurring_failure_threshold:
                recurring.append(
                    self._finding(
                        "RECURRING_FAILURE",
                        "CRITICAL",
                        f"Failure family `{family}` has survived {repeat_count} candidate attempts.",
                        reproducible=True,
                        token=fingerprint,
                        repeat_count=repeat_count,
                        evidence_state="VERIFIED",
                        family_fingerprint=f"RECURRING_FAILURE:{family}",
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
                "state": finding["state"],
                "fingerprint": finding["fingerprint"],
                "family_fingerprint": finding["family_fingerprint"],
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
        evidence_state: str | None = None,
        family_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        fingerprint = f"{klass}:{token or self._short_hash(evidence)}"
        state = evidence_state or ("VERIFIED" if reproducible else "SUPPORTED")
        out = {
            "class": klass,
            "severity": severity,
            "evidence": evidence,
            "reproducible": reproducible,
            "state": state,
            "fingerprint": fingerprint,
            "family_fingerprint": family_fingerprint or fingerprint,
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
