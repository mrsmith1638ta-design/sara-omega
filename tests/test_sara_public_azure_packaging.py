from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sara_public_runtime_keeps_its_acceptance_boundary():
    source = (ROOT / "sara_public.py").read_text(encoding="utf-8")

    assert "This is a new commercial product, not SARA-OMEGA production." in source
    assert "Production acceptance remains UNVERIFIED" in source
    assert '"production_acceptance": "UNVERIFIED"' in source


def test_sara_public_azure_container_contract_is_isolated():
    requirements = (ROOT / "requirements-sara-public.txt").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile.sara-public").read_text(encoding="utf-8")

    for dependency in (
        "fastapi==0.115.6",
        "uvicorn[standard]==0.34.0",
        "httpx==0.28.1",
        "cryptography>=48,<51",
        "stripe",
        "PyJWT",
        "pydantic==2.10.5",
    ):
        assert dependency in requirements

    assert "requirements-sara-public.txt" in dockerfile
    assert 'CMD ["python", "sara_public.py", "--serve"]' in dockerfile
    assert "/health" in dockerfile
