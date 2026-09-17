import json


def test_benchmark_summary_computes_latency_percentiles():
    from tools.voice_1_1_benchmark import summarize_latencies

    summary = summarize_latencies([100, 200, 300, 400])

    assert summary["count"] == 4
    assert summary["p50_ms"] == 250
    assert summary["max_ms"] == 400


def test_acceptance_evidence_references_voice_1_0_without_mutating_it(tmp_path):
    from tools.voice_1_1_acceptance_probe import build_acceptance_evidence

    capsule = tmp_path / "voice-1-0.md"
    capsule.write_text("immutable voice 1.0", encoding="utf-8")

    evidence = build_acceptance_evidence(
        voice_1_0_capsule=str(capsule),
        source_commit_sha="implementation-sha",
        deployment_id="deployment-id",
        job_receipt={"job_id": "voice-job-1"},
        benchmark={"count": 1},
        restart_persistence={"reused_existing_model": True},
        road={"production_accepted": True},
    )

    assert evidence["voice_1_0_capsule"] == str(capsule)
    assert evidence["voice_1_0_capsule_sha256"]
    assert evidence["voice_1_1"]["source_commit_sha"] == "implementation-sha"
    assert capsule.read_text(encoding="utf-8") == "immutable voice 1.0"
    assert "secret" not in json.dumps(evidence).lower()
