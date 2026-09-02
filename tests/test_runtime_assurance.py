import asyncio

from app.runtime_assurance import (
    ReceiptVerifyRequest,
    RuntimeAssuranceEngine,
    RuntimeAssuranceRequest,
)


def engine():
    return RuntimeAssuranceEngine({"SARA_RUNTIME_ASSURANCE_SECRET": "test-secret"})


def test_blocks_false_live_module_claim():
    result = asyncio.run(engine().verify_output(
        RuntimeAssuranceRequest(
            module="sara-voice-ui",
            output="sara-module-registry is live in Cloud Run.",
            context={
                "live_module_truth": {
                    "source": "cloud_run_inventory",
                    "modules": {"sara-module-registry": {"live": False}},
                }
            },
        )
    ))

    assert result["verdict"] == "BLOCK"
    assert result["action"] == "suppress"
    assert result["suppression"]["applied"] is True
    assert result["claims"][0]["status"] == "contradicted"


def test_blocks_false_all_module_enforcement_claim():
    result = asyncio.run(engine().verify_output(
        RuntimeAssuranceRequest(
            module="sara-governance",
            output="All 215 SARA modules are enforced by runtime truth verification.",
            context={
                "live_module_truth": {
                    "source": "cloud_run_inventory",
                    "live_count": 202,
                    "historical_count": 215,
                    "enforcement_count": 2,
                }
            },
        )
    ))

    assert result["verdict"] == "BLOCK"
    assert result["claims"][0]["status"] == "contradicted"


def test_blocks_missing_financial_adapter_under_fail_closed_policy():
    result = asyncio.run(engine().verify_output(
        RuntimeAssuranceRequest(
            module="sara-finance",
            output="Apple AAPL has revenue reported in an SEC filing.",
            context={},
        )
    ))

    assert result["verdict"] == "BLOCK"
    assert result["claims"][0]["status"] == "unavailable"
    assert "financial" in result["claims"][0]["domains"]


def test_blocks_missing_data_analytics_adapter_under_fail_closed_policy():
    result = asyncio.run(engine().verify_output(
        RuntimeAssuranceRequest(
            module="sara-analytics",
            output="The dashboard shows churn increased by 12 percent.",
            context={},
        )
    ))

    assert result["verdict"] == "BLOCK"
    assert result["claims"][0]["status"] == "unavailable"
    assert "data_analytics" in result["claims"][0]["domains"]


def test_allows_supported_data_analytics_claim_with_adapter():
    result = asyncio.run(engine().verify_output(
        RuntimeAssuranceRequest(
            module="sara-analytics",
            output="The dashboard shows churn increased by 12 percent.",
            context={
                "evidence_adapters": {
                    "data_analytics": {
                        "verdict": "supported",
                        "confidence": 0.88,
                        "source": "warehouse metrics adapter",
                    }
                }
            },
        )
    ))

    assert result["verdict"] == "ALLOW"
    assert result["claims"][0]["status"] == "supported"


def test_allows_supported_medical_claim_with_audit_receipt():
    assurance = engine()
    result = asyncio.run(assurance.verify_output(
        RuntimeAssuranceRequest(
            module="sara-medical",
            output="Aspirin may have side effects.",
            context={
                "evidence_adapters": {
                    "medical": {
                        "verdict": "supported",
                        "confidence": 0.91,
                        "source": "openFDA label adapter",
                        "evidence": [{"title": "Aspirin label warnings"}],
                    }
                }
            },
        )
    ))

    assert result["verdict"] == "ALLOW"
    assert result["claims"][0]["status"] == "supported"
    assert result["audit_receipt"]["signature"]
    verified = assurance.verify_receipt(ReceiptVerifyRequest(receipt=result["audit_receipt"]))
    assert verified["valid"] is True


def test_blocks_adapter_contradiction():
    result = asyncio.run(engine().verify_output(
        RuntimeAssuranceRequest(
            module="sara-legal",
            output="21 CFR contains no federal regulations.",
            context={
                "evidence_adapters": {
                    "legal": {
                        "verdict": "contradicted",
                        "confidence": 0.93,
                        "source": "eCFR adapter",
                    }
                }
            },
        )
    ))

    assert result["verdict"] == "BLOCK"
    assert result["claims"][0]["status"] == "contradicted"


def test_receipt_tampering_fails_verification():
    assurance = engine()
    result = asyncio.run(assurance.verify_output(
        RuntimeAssuranceRequest(
            module="sara-medical",
            output="Aspirin may have side effects.",
            context={"evidence_adapters": {"medical": {"verdict": "supported"}}},
        )
    ))
    tampered = dict(result["audit_receipt"])
    tampered["verdict"] = "ALLOW" if tampered["verdict"] != "ALLOW" else "BLOCK"

    verified = assurance.verify_receipt(ReceiptVerifyRequest(receipt=tampered))

    assert verified["valid"] is False
    assert verified["signature_ok"] is False
