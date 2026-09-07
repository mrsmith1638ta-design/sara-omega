import json
import pytest


def test_registry_rejects_duplicate_equation_ids(tmp_path):
    from app.science.registry import RegistryError, ScienceRegistry

    equations = [
        {"id":"x","domain":"engineering","name":"X","symbolic_form":"x","provenance_class":"ENGINEERING_MODEL","source_ids":["s"],"variables":{},"units":{},"applicability":"test","limitations":[]},
        {"id":"x","domain":"engineering","name":"X2","symbolic_form":"x2","provenance_class":"ENGINEERING_MODEL","source_ids":["s"],"variables":{},"units":{},"applicability":"test","limitations":[]},
    ]
    sources = [{"id":"s","title":"Source","domain":"engineering","source_type":"reference","provenance_class":"ESTABLISHED_PHYSICS","evidence_status":"SUPPORTED"}]
    ep = tmp_path / "equations.json"; sp = tmp_path / "sources.json"
    ep.write_text(json.dumps(equations)); sp.write_text(json.dumps(sources))
    with pytest.raises(RegistryError):
        ScienceRegistry(ep, sp)


def test_core_registry_contains_required_equations():
    from app.science.registry import ScienceRegistry
    registry = ScienceRegistry.default()
    for equation_id in ["egypt.seked", "egypt.frustum", "physics.drag_force", "physics.drag_power", "control.state_space", "maglev.ems_force_simplified"]:
        assert registry.get_equation(equation_id)["id"] == equation_id
