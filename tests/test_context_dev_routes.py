"""Static route-wiring tests that do not initialize external cloud clients."""

from __future__ import annotations

import ast
from pathlib import Path

MAIN_PATH = Path(__file__).resolve().parents[1] / "main.py"


def _main_tree() -> ast.Module:
    return ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))


def _route_paths(function: ast.FunctionDef) -> set[str]:
    paths: set[str] = set()
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call) or not decorator.args:
            continue
        first = decorator.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            paths.add(first.value)
    return paths


def _functions() -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in _main_tree().body
        if isinstance(node, ast.FunctionDef)
    }


def test_context_dev_routes_are_registered_without_importing_runtime():
    functions = _functions()
    assert "/context-dev/status" in _route_paths(functions["context_dev_status"])
    assert "/context-dev/evaluate" in _route_paths(functions["context_dev_evaluate"])


def test_owner_evaluation_route_calls_fail_closed_resolver():
    source = ast.unparse(_functions()["context_dev_evaluate"])
    assert "authorize(req) != 'owner'" in source
    assert "evaluate_request(" in source
    assert "CONTEXT_DEV_LICENSE" in source


def test_main_exposes_context_dev_state_in_health():
    source = ast.unparse(_functions()["health"])
    assert "context_dev_policy_gate" in source
    assert "CONTEXT_DEV_LICENSE.public_status()" in source
    assert "CONTEXT_DEV_LICENSE.commercial_runtime_authorized()" in source


def test_main_loads_reviewed_context_dev_license_instead_of_pending_constant():
    module_source = MAIN_PATH.read_text(encoding="utf-8")
    assert "load_context_dev_license" in module_source
    assert "CONTEXT_DEV_LICENSE = load_context_dev_license()" in module_source
    assert "CONTEXT_DEV_LICENSE = PENDING_CONTEXT_DEV_LICENSE" not in module_source
