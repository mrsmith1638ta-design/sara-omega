def test_orchestrator_extracts_truth_gate_claims_and_decisions():
    from app.orchestrator import SaraOmega

    analyses = [
        {
            "domain": "maglev_eds",
            "execution_authority": False,
            "metadata": {
                "truth_gate": {
                    "claims": [
                        {
                            "claim_text": "maglev_eds:maglev.eds_characteristic",
                            "provenance_class": "ENGINEERING_MODEL",
                            "evidence_status": "SUPPORTED",
                            "applicability_scope": "ARCHITECTURE_SPECIFIC",
                            "certainty_level": "SUPPORTED",
                            "dependency_conditions": ["guideway topology"],
                            "source_ids": ["maglev.eds"],
                            "assumptions": [],
                            "limitations": [],
                            "validation_status": "VALID",
                            "universality_status": "SYSTEM_DEPENDENT",
                            "certainty_ceiling": "INFERRED",
                        }
                    ],
                    "decisions": [
                        {
                            "claim_text": "maglev_eds:maglev.eds_characteristic",
                            "original_certainty": "SUPPORTED",
                            "gated_certainty": "INFERRED",
                            "universality_status": "SYSTEM_DEPENDENT",
                            "disposition": "QUALIFIED",
                            "reasons": ["certainty capped by claim ceiling"],
                            "applicability_scope": "ARCHITECTURE_SPECIFIC",
                            "provenance_class": "ENGINEERING_MODEL",
                            "source_ids": ["maglev.eds"],
                        }
                    ],
                }
            },
        }
    ]

    claims, decisions = SaraOmega._science_truth_gate_data(analyses)

    assert len(claims) == 1
    assert claims[0].universality_status.value == "SYSTEM_DEPENDENT"
    assert decisions[0]["gated_certainty"] == "INFERRED"
