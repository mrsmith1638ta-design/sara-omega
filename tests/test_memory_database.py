import shutil

from app.memory import DecisionLedger
from app.models import Disposition, GovernanceDecision, Problem, Verdict


def test_decision_ledger_closes_sqlite_connections(monkeypatch, tmp_path):
    monkeypatch.setenv("SARA_DATA_DIR", str(tmp_path))
    ledger = DecisionLedger()
    problem = Problem(
        query="Analyze dataset values 5, 10, and 15 for mean.",
        context={"dataset": [5, 10, 15]},
    )
    verdict = Verdict(
        decision="ANSWER",
        why="Dataset mean is 10.",
        confidence=0.9,
        next_action="return_result",
        governance=GovernanceDecision(disposition=Disposition.ALLOW),
        providers_used=["data_analytics"],
    )

    decision_id = ledger.record(problem, verdict)
    ledger.record_outcome(
        decision_id,
        {"accepted": True, "dataset_case": "mean"},
        "Persisted dataset decision.",
    )

    recent = ledger.recent(5)

    assert recent[0]["id"] == decision_id
    assert recent[0]["outcome"]["accepted"] is True
    shutil.rmtree(tmp_path)
