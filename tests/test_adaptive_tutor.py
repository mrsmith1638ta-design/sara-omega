import pytest
from fastapi.testclient import TestClient

from SARA_AI_Product_Manager_Adaptive_Tutor_UNIFIED import (
    AnswerSealer,
    MasteryEngine,
    MasteryState,
    RoadVerifierClient,
    SaraQuestionClient,
    SemanticDuplicateGate,
    Store,
    TutorService,
    create_app,
)


class FakeSaraClient(SaraQuestionClient):
    def __init__(self, question):
        self.question = question

    async def generate_question(self, competency, difficulty, learner_context):
        generated = dict(self.question)
        generated["competency"] = competency
        generated["difficulty"] = difficulty
        return generated


class FakeRoadClient(RoadVerifierClient):
    async def verify_question(self, question):
        return {"status": "PASS", "verified": True}


def make_question():
    return {
        "prompt": "A team sees activation rise while paid conversion drops. What should the PM do first?",
        "choices": [
            "Segment the funnel and inspect activation quality by acquisition channel.",
            "Declare the onboarding experiment successful and scale paid acquisition.",
            "Remove pricing from the funnel until activation reaches its target.",
            "Ignore conversion because activation is the leading metric.",
        ],
        "correct_index": 0,
        "explanation": "Activation and conversion are in tension, so the PM should diagnose segment quality before scaling.",
        "reasoning_archetype": "metric_tradeoff_root_cause",
        "evidence_notes": "Tests tradeoff reasoning between activation and paid conversion.",
    }


def make_service(tmp_path):
    return TutorService(
        store=Store(str(tmp_path / "tutor.db")),
        sara=FakeSaraClient(make_question()),
        road=FakeRoadClient("https://road.example/verify", "token"),
        sealer=AnswerSealer(b"x" * 32),
    )


def test_answer_sealer_accepts_only_the_committed_choice():
    sealer = AnswerSealer(b"x" * 32)
    commitment = sealer.seal("question-1", 2)

    assert sealer.verify("question-1", 2, commitment)
    assert not sealer.verify("question-1", 1, commitment)
    assert not sealer.verify("question-2", 2, commitment)


def test_semantic_gate_rejects_exact_and_reasoning_duplicates():
    gate = SemanticDuplicateGate()
    choices = ["A", "B", "C", "D"]
    gate.remember(
        "Which metric should a product manager inspect before launch?",
        choices,
        "launch_metric_tradeoff",
    )

    assert gate.is_duplicate(
        "Which metric should a product manager inspect before launch?",
        choices,
        "new_reasoning",
    )
    assert gate.is_duplicate(
        "A different surface question",
        ["W", "X", "Y", "Z"],
        "launch_metric_tradeoff",
    )
    assert not gate.is_duplicate(
        "How should a team evaluate retrieval quality for a support copilot?",
        ["A", "B", "C", "D"],
        "rag_evaluation",
    )


def test_mastery_engine_advances_on_first_try_correct_and_regresses_on_wrong_answer():
    engine = MasteryEngine(["metrics_analytics"])
    state = MasteryState("metrics_analytics", mastery=0.5, difficulty=2)

    improved = engine.update(state, correct=True, first_try=True)
    regressed = engine.update(improved, correct=False, first_try=False)

    assert improved.mastery == pytest.approx(0.6)
    assert improved.first_try_correct == 1
    assert improved.eventual_correct == 1
    assert regressed.mastery == pytest.approx(0.48)
    assert regressed.streak == 0


@pytest.mark.asyncio
async def test_service_generates_question_without_exposing_answer(tmp_path):
    service = make_service(tmp_path)

    question = await service.next_question("learner-1")

    assert question["question_id"]
    assert question["competency"] in service.mastery_engine.competencies
    assert "correct_index" not in question
    assert "explanation" not in question


def test_answer_requires_correct_choice_to_advance(tmp_path):
    service = make_service(tmp_path)
    client = TestClient(create_app(service))

    question = client.post("/v1/session/learner-1/questions/next").json()

    wrong = client.post(
        f"/v1/session/learner-1/questions/{question['question_id']}/answer",
        json={"choice_index": 1},
    )
    right = client.post(
        f"/v1/session/learner-1/questions/{question['question_id']}/answer",
        json={"choice_index": 0},
    )

    assert wrong.status_code == 200
    assert wrong.json()["advance"] is False
    assert "try again" in wrong.json()["explanation"]
    assert right.status_code == 200
    assert right.json()["advance"] is True
    assert right.json()["correct"] is True
