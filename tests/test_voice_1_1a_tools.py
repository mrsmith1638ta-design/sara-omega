import json

import pytest


def test_evidence_hashes_both_immutable_baselines_without_mutation(tmp_path):
    from tools.voice_1_1a_acceptance_probe import build_voice_1_1a_evidence

    voice_1_0 = tmp_path / "voice-1-0.json"
    voice_1_1 = tmp_path / "voice-1-1.json"
    voice_1_0.write_text("v1.0", encoding="utf-8")
    voice_1_1.write_text("v1.1", encoding="utf-8")

    evidence = build_voice_1_1a_evidence(
        voice_1_0_paths=[str(voice_1_0)],
        voice_1_1_paths=[str(voice_1_1)],
        source_commit_sha="a" * 40,
        sara_deployment_id="ffa3e879-a610-4d57-885b-e76de546fcf5",
        piper_deployment_id="0a831729-4f80-4981-ae17-a888108ef82e",
        transaction={"audio_sha256": "b" * 64},
        entitlement={"status": "PASS"},
        isolation={"status": "PASS"},
        limits={"status": "PASS"},
        privacy={"status": "PASS"},
        restart={"status": "PASS"},
        road={"status": "PASS"},
    )

    assert evidence["evidence_type"] == "sara-omega-voice-1-1a-acceptance"
    assert evidence["immutable_baselines"]["voice_1_0"][0]["sha256"]
    assert evidence["immutable_baselines"]["voice_1_1"][0]["sha256"]
    assert evidence["records_sensitive_values"] is False
    assert voice_1_0.read_text(encoding="utf-8") == "v1.0"
    assert voice_1_1.read_text(encoding="utf-8") == "v1.1"


def test_evidence_rejects_invalid_commit_and_sensitive_content(tmp_path):
    from tools.voice_1_1a_acceptance_probe import build_voice_1_1a_evidence

    baseline = tmp_path / "baseline.json"
    baseline.write_text("accepted", encoding="utf-8")
    kwargs = dict(
        voice_1_0_paths=[str(baseline)],
        voice_1_1_paths=[str(baseline)],
        source_commit_sha="not-a-commit",
        sara_deployment_id="sara-deploy",
        piper_deployment_id="piper-deploy",
        transaction={},
        entitlement={},
        isolation={},
        limits={},
        privacy={},
        restart={},
        road={"status": "PASS"},
    )
    with pytest.raises(ValueError, match="source_commit_sha"):
        build_voice_1_1a_evidence(**kwargs)

    kwargs["source_commit_sha"] = "a" * 40
    kwargs["privacy"] = {"oauth_token": "must-not-appear"}
    with pytest.raises(ValueError, match="sensitive evidence key"):
        build_voice_1_1a_evidence(**kwargs)


def test_evidence_rejects_private_urls_internal_ids_and_supplied_sensitive_values(tmp_path):
    from tools.voice_1_1a_acceptance_probe import build_voice_1_1a_evidence

    baseline = tmp_path / "baseline.json"
    baseline.write_text("accepted", encoding="utf-8")
    common = dict(
        voice_1_0_paths=[str(baseline)],
        voice_1_1_paths=[str(baseline)],
        source_commit_sha="a" * 40,
        sara_deployment_id="sara-deploy",
        piper_deployment_id="piper-deploy",
        entitlement={},
        isolation={},
        limits={},
        privacy={},
        restart={},
        road={"status": "PASS"},
    )
    with pytest.raises(ValueError, match="private URL"):
        build_voice_1_1a_evidence(
            **common,
            transaction={"service": "http://voice.internal:8080"},
        )
    with pytest.raises(ValueError, match="internal identity"):
        build_voice_1_1a_evidence(
            **common,
            transaction={"user_uuid": "00000000-0000-4000-8000-000000000001"},
        )
    with pytest.raises(ValueError, match="sensitive evidence value"):
        build_voice_1_1a_evidence(
            **common,
            transaction={"note": "certification transcript"},
            sensitive_values=["certification transcript"],
        )


def test_evidence_is_json_serializable_and_does_not_use_secret_key_names(tmp_path):
    from tools.voice_1_1a_acceptance_probe import build_voice_1_1a_evidence

    baseline = tmp_path / "baseline.json"
    baseline.write_text("accepted", encoding="utf-8")
    evidence = build_voice_1_1a_evidence(
        voice_1_0_paths=[str(baseline)],
        voice_1_1_paths=[str(baseline)],
        source_commit_sha="a" * 40,
        sara_deployment_id="sara-deploy",
        piper_deployment_id="piper-deploy",
        transaction={},
        entitlement={},
        isolation={},
        limits={},
        privacy={},
        restart={},
        road={"status": "PASS"},
    )

    serialized = json.dumps(evidence, sort_keys=True)
    assert "secret" not in serialized.lower()
    assert "bearer" not in serialized.lower()


def test_evidence_allows_bounded_transcript_control_metadata(tmp_path):
    from tools.voice_1_1a_acceptance_probe import build_voice_1_1a_evidence

    baseline = tmp_path / "baseline.json"
    baseline.write_text("accepted", encoding="utf-8")

    evidence = build_voice_1_1a_evidence(
        voice_1_0_paths=[str(baseline)],
        voice_1_1_paths=[str(baseline)],
        source_commit_sha="a" * 40,
        sara_deployment_id="sara-deploy",
        piper_deployment_id="piper-deploy",
        transaction={},
        entitlement={},
        isolation={},
        limits={},
        privacy={"transcript_encrypted": True, "transcript_plaintext_found": False},
        restart={},
        road={"status": "PASS"},
    )

    assert evidence["voice_1_1a"]["privacy"]["transcript_encrypted"] is True
