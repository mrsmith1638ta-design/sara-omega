import math
import pytest


def test_drag_and_power_scale_correctly():
    from app.science.engineering import EngineeringPhysicsEngine
    e = EngineeringPhysicsEngine()
    f1 = e.drag_force(rho=1.225, cd=0.2, area=10.0, velocity=100.0)
    f2 = e.drag_force(rho=1.225, cd=0.2, area=10.0, velocity=200.0)
    assert math.isclose(f2 / f1, 4.0, rel_tol=1e-12)
    p1 = e.drag_power(rho=1.225, cd=0.2, area=10.0, velocity=100.0)
    p2 = e.drag_power(rho=1.225, cd=0.2, area=10.0, velocity=200.0)
    assert math.isclose(p2 / p1, 8.0, rel_tol=1e-12)


def test_static_equilibrium_and_invalid_inputs():
    from app.science.engineering import EngineeringPhysicsEngine
    from app.science.validation import ScienceValidationError
    e = EngineeringPhysicsEngine()
    assert e.force_balance([10, -4, -6]) == 0
    with pytest.raises(ScienceValidationError):
        e.drag_force(rho=1.225, cd=0.2, area=-1.0, velocity=100.0)
