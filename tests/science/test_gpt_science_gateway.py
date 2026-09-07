from main import app


def test_science_has_no_unrestricted_bypass_endpoint():
    paths = set(app.openapi()["paths"])
    assert "/science/solve" not in paths
    assert "/gpt/action/gateway" in paths
