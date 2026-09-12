"""SARA AI Product Manager Adaptive Tutor unified runtime."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import random
import re
import sqlite3
import threading
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ValidationError, field_validator

COMPETENCIES = [
    "product_foundations",
    "customer_discovery",
    "product_strategy",
    "prioritization",
    "prd_requirements",
    "agile_delivery",
    "metrics_analytics",
    "ai_economics",
    "rag",
    "llm_product_design",
    "ai_evaluation",
    "ai_security",
    "responsible_ai",
    "stakeholder_management",
    "release_governance",
    "commercialization",
    "road_framework",
]


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(
        r"\b(?:sara|ai|product|manager|the|a|an|is|are|for|to|of|in|on|with|and|or)\b",
        " ",
        text,
    )
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return " ".join(text.split())


def tokens(text: str) -> set[str]:
    return set(normalize(text).split())


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class Fingerprint:
    exact: str
    qtoks: frozenset[str]
    reasoning: str


class SemanticDuplicateGate:
    def __init__(self, threshold: float = 0.72):
        if not 0 <= threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        self.threshold = threshold
        self.items: list[Fingerprint] = []

    def _fingerprint(self, question: str, answers: list[str], reasoning: str) -> Fingerprint:
        exact_material = normalize(question) + "|" + normalize("|".join(answers))
        return Fingerprint(
            exact=hashlib.sha256(exact_material.encode()).hexdigest(),
            qtoks=frozenset(tokens(question)),
            reasoning=normalize(reasoning),
        )

    def remember(self, question: str, answers: list[str], reasoning: str) -> None:
        self.items.append(self._fingerprint(question, answers, reasoning))

    def is_duplicate(self, question: str, answers: list[str], reasoning: str) -> bool:
        candidate = self._fingerprint(question, answers, reasoning)
        for previous in self.items:
            if candidate.exact == previous.exact:
                return True
            if jaccard(set(candidate.qtoks), set(previous.qtoks)) >= self.threshold:
                return True
            if candidate.reasoning and candidate.reasoning == previous.reasoning:
                return True
        return False


@dataclass
class MasteryState:
    competency: str
    attempts: int = 0
    first_try_correct: int = 0
    eventual_correct: int = 0
    streak: int = 0
    mastery: float = 0.25
    difficulty: int = 1


class MasteryEngine:
    def __init__(self, competencies: list[str]):
        self.competencies = competencies

    def update(self, state: MasteryState, correct: bool, first_try: bool) -> MasteryState:
        updated = MasteryState(**state.__dict__)
        updated.attempts += 1
        if correct:
            updated.eventual_correct += 1
            if first_try:
                updated.first_try_correct += 1
            updated.streak += 1
            updated.mastery = min(1.0, updated.mastery + (0.10 if first_try else 0.05))
            if updated.streak >= 4 and updated.mastery >= 0.55:
                updated.difficulty = min(5, updated.difficulty + 1)
                updated.streak = 0
        else:
            updated.streak = 0
            updated.mastery = max(0.0, updated.mastery - 0.12)
            if updated.mastery < 0.35:
                updated.difficulty = max(1, updated.difficulty - 1)
        return updated

    def choose(self, states: dict[str, MasteryState]) -> MasteryState:
        pool = [states.get(name, MasteryState(name)) for name in self.competencies]
        weights = [max(0.05, 1.05 - state.mastery) for state in pool]
        return random.choices(pool, weights=weights, k=1)[0]


class ProviderError(RuntimeError):
    pass


class ProviderContractError(ProviderError):
    pass


class GeneratedQuestion(BaseModel):
    prompt: str = Field(min_length=20, max_length=5000)
    choices: list[str]
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=5, max_length=5000)
    competency: str = Field(min_length=2, max_length=100)
    difficulty: int = Field(ge=1, le=5)
    reasoning_archetype: str = Field(min_length=2, max_length=200)
    evidence_notes: str = Field(min_length=1, max_length=5000)

    @field_validator("choices")
    @classmethod
    def validate_choices(cls, value: list[str]) -> list[str]:
        if len(value) != 4:
            raise ValueError("exactly four choices required")
        if any(not isinstance(item, str) or not item.strip() or len(item) > 3000 for item in value):
            raise ValueError("invalid choice")
        if len({item.strip().casefold() for item in value}) != 4:
            raise ValueError("choices must be distinct")
        return value


class RoadVerdict(BaseModel):
    status: str
    verified: bool
    reason: str | None = None


class SaraQuestionClient:
    def __init__(self, url: str, token: str, timeout: float = 20.0, transport: Any = None):
        if not url or not token:
            raise ValueError("SARA url and token required")
        self.url = url
        self.token = token
        self.timeout = timeout
        self.transport = transport

    async def generate_question(self, competency: str, difficulty: int, learner_context: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "task": "generate_ai_product_manager_assessment_item",
            "requirements": {
                "competency": competency,
                "difficulty": difficulty,
                "format": "multiple_choice",
                "choice_count": 4,
                "exactly_one_correct": True,
                "novel_reasoning_required": True,
                "no_surface_rewrites": True,
                "return_json_only": True,
            },
            "learner_context": learner_context,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport, follow_redirects=False) as client:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                )
            response.raise_for_status()
            if len(response.content) > 200_000:
                raise ProviderContractError("SARA response too large")
            return GeneratedQuestion.model_validate(response.json()).model_dump()
        except ProviderContractError:
            raise
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise ProviderContractError(f"SARA generation failed contract: {exc}") from exc


class RoadVerifierClient:
    def __init__(self, url: str, token: str, timeout: float = 15.0, transport: Any = None):
        if not url or not token:
            raise ValueError("ROAD url and token required")
        self.url = url
        self.token = token
        self.timeout = timeout
        self.transport = transport

    async def verify_question(self, question: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "task": "verify_ai_product_manager_assessment_item",
            "question": question,
            "checks": [
                "single_defensible_answer",
                "distractors_materially_wrong",
                "current_terminology",
                "no_unsupported_sara_claims",
                "explanation_supports_answer",
                "difficulty_matches",
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport, follow_redirects=False) as client:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                )
            response.raise_for_status()
            if len(response.content) > 100_000:
                raise ProviderContractError("ROAD response too large")
            return RoadVerdict.model_validate(response.json()).model_dump()
        except ProviderContractError:
            raise
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise ProviderContractError(f"ROAD verification failed contract: {exc}") from exc


class AnswerSealer:
    def __init__(self, secret: bytes):
        if len(secret) < 32:
            raise ValueError("secret must be at least 32 bytes")
        self.secret = secret

    def seal(self, question_id: str, choice_index: int) -> str:
        material = f"{question_id}:{choice_index}".encode()
        return hmac.new(self.secret, material, hashlib.sha256).hexdigest()

    def verify(self, question_id: str, choice_index: int, commitment: str) -> bool:
        return hmac.compare_digest(self.seal(question_id, choice_index), commitment)


class Store:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS mastery(
                    learner_id TEXT NOT NULL,
                    competency TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    first_try_correct INTEGER NOT NULL,
                    eventual_correct INTEGER NOT NULL,
                    streak INTEGER NOT NULL,
                    mastery REAL NOT NULL,
                    difficulty INTEGER NOT NULL,
                    PRIMARY KEY(learner_id, competency)
                );
                CREATE TABLE IF NOT EXISTS questions(
                    id TEXT PRIMARY KEY,
                    learner_id TEXT NOT NULL,
                    competency TEXT NOT NULL,
                    difficulty INTEGER NOT NULL,
                    prompt TEXT NOT NULL,
                    choices_json TEXT NOT NULL,
                    answer_commitment TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    reasoning TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    answered_correctly INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS attempts(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    learner_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    choice_index INTEGER NOT NULL,
                    correct INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS semantic_index(
                    fingerprint TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    choices_json TEXT NOT NULL,
                    reasoning TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def save_mastery(self, learner_id: str, state: MasteryState) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO mastery VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(learner_id, competency) DO UPDATE SET
                    attempts=excluded.attempts,
                    first_try_correct=excluded.first_try_correct,
                    eventual_correct=excluded.eventual_correct,
                    streak=excluded.streak,
                    mastery=excluded.mastery,
                    difficulty=excluded.difficulty
                """,
                (
                    learner_id,
                    state.competency,
                    state.attempts,
                    state.first_try_correct,
                    state.eventual_correct,
                    state.streak,
                    state.mastery,
                    state.difficulty,
                ),
            )

    def get_mastery(self, learner_id: str) -> dict[str, MasteryState]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT * FROM mastery WHERE learner_id=?", (learner_id,)).fetchall()
        return {
            row["competency"]: MasteryState(
                competency=row["competency"],
                attempts=row["attempts"],
                first_try_correct=row["first_try_correct"],
                eventual_correct=row["eventual_correct"],
                streak=row["streak"],
                mastery=row["mastery"],
                difficulty=row["difficulty"],
            )
            for row in rows
        }

    def save_question(self, record: dict[str, Any]) -> None:
        choices_json = json.dumps(record["choices"])
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO questions(
                    id, learner_id, competency, difficulty, prompt,
                    choices_json, answer_commitment, explanation,
                    reasoning, fingerprint
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record["id"],
                    record["learner_id"],
                    record["competency"],
                    record["difficulty"],
                    record["prompt"],
                    choices_json,
                    record["answer_commitment"],
                    record["explanation"],
                    record["reasoning"],
                    record["fingerprint"],
                ),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO semantic_index(
                    fingerprint, prompt, choices_json, reasoning
                ) VALUES(?,?,?,?)
                """,
                (record["fingerprint"], record["prompt"], choices_json, record["reasoning"]),
            )

    def get_question(self, question_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["choices"] = json.loads(data.pop("choices_json"))
        return data

    def mark_attempt(self, learner_id: str, question_id: str, choice_index: int, correct: bool) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO attempts(learner_id, question_id, choice_index, correct) VALUES(?,?,?,?)",
                (learner_id, question_id, choice_index, int(correct)),
            )
            if correct:
                connection.execute("UPDATE questions SET answered_correctly=1 WHERE id=?", (question_id,))

    def attempts_for_question(self, learner_id: str, question_id: str) -> int:
        with self._lock, self._connect() as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM attempts WHERE learner_id=? AND question_id=?",
                    (learner_id, question_id),
                ).fetchone()[0]
            )

    def semantic_items(self, limit: int = 5000) -> list[sqlite3.Row]:
        with self._lock, self._connect() as connection:
            return connection.execute(
                "SELECT prompt, choices_json, reasoning FROM semantic_index ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()


class GenerationBlocked(RuntimeError):
    pass


class QuestionNotFound(KeyError):
    pass


class QuestionAlreadyCompleted(RuntimeError):
    pass


class TutorService:
    def __init__(
        self,
        store: Store,
        sara: SaraQuestionClient,
        road: RoadVerifierClient,
        sealer: AnswerSealer,
        max_generation_attempts: int = 8,
        duplicate_threshold: float = 0.72,
    ):
        if max_generation_attempts < 1:
            raise ValueError("max_generation_attempts must be positive")
        self.store = store
        self.sara = sara
        self.road = road
        self.sealer = sealer
        self.max_generation_attempts = max_generation_attempts
        self.duplicate_threshold = duplicate_threshold
        self.mastery_engine = MasteryEngine(COMPETENCIES)

    def _gate_from_store(self) -> SemanticDuplicateGate:
        gate = SemanticDuplicateGate(self.duplicate_threshold)
        for row in self.store.semantic_items():
            gate.remember(row["prompt"], json.loads(row["choices_json"]), row["reasoning"])
        return gate

    def _learner_context(self, learner_id: str, states: dict[str, MasteryState], target: MasteryState) -> dict[str, Any]:
        weakest = sorted(states.values(), key=lambda item: item.mastery)[:5]
        return {
            "learner_id_hash": hashlib.sha256(learner_id.encode()).hexdigest()[:16],
            "target_competency": target.competency,
            "target_difficulty": target.difficulty,
            "weak_competencies": [
                {"competency": state.competency, "mastery": round(state.mastery, 3)}
                for state in weakest
            ],
            "instruction": (
                "Create a genuinely new reasoning problem, not a paraphrase of a common definition question. "
                "Vary domain, constraints, evidence, tradeoffs, stakeholder conflict, metrics, lifecycle stage, "
                "and decision objective. Do not reuse a prior reasoning archetype."
            ),
        }

    async def next_question(self, learner_id: str) -> dict[str, Any]:
        states = self.store.get_mastery(learner_id)
        target = self.mastery_engine.choose(states)
        gate = self._gate_from_store()
        for _ in range(self.max_generation_attempts):
            candidate = await self.sara.generate_question(
                target.competency,
                target.difficulty,
                self._learner_context(learner_id, states, target),
            )
            if candidate["competency"] != target.competency:
                continue
            if candidate["difficulty"] != target.difficulty:
                continue
            if gate.is_duplicate(candidate["prompt"], candidate["choices"], candidate["reasoning_archetype"]):
                continue
            verdict = await self.road.verify_question(candidate)
            if verdict.get("status") != "PASS" or verdict.get("verified") is not True:
                raise GenerationBlocked("ROAD did not verify generated question")
            question_id = str(uuid.uuid4())
            correct_index = int(candidate["correct_index"])
            semantic_fingerprint = hashlib.sha256(
                (normalize(candidate["prompt"]) + "|" + normalize(candidate["reasoning_archetype"])).encode()
            ).hexdigest()
            self.store.save_question(
                {
                    "id": question_id,
                    "learner_id": learner_id,
                    "competency": candidate["competency"],
                    "difficulty": candidate["difficulty"],
                    "prompt": candidate["prompt"],
                    "choices": candidate["choices"],
                    "answer_commitment": self.sealer.seal(question_id, correct_index),
                    "explanation": candidate["explanation"],
                    "reasoning": candidate["reasoning_archetype"],
                    "fingerprint": semantic_fingerprint,
                }
            )
            return {
                "question_id": question_id,
                "prompt": candidate["prompt"],
                "choices": candidate["choices"],
                "competency": candidate["competency"],
                "difficulty": candidate["difficulty"],
            }
        raise GenerationBlocked("Unable to generate a sufficiently novel ROAD-verified question within bounded attempts")

    def answer(self, learner_id: str, question_id: str, choice_index: int) -> dict[str, Any]:
        if choice_index not in (0, 1, 2, 3):
            raise ValueError("choice_index must be 0..3")
        question = self.store.get_question(question_id)
        if question is None or question["learner_id"] != learner_id:
            raise QuestionNotFound(question_id)
        if question["answered_correctly"]:
            raise QuestionAlreadyCompleted(question_id)
        prior_attempts = self.store.attempts_for_question(learner_id, question_id)
        correct = self.sealer.verify(question_id, choice_index, question["answer_commitment"])
        self.store.mark_attempt(learner_id, question_id, choice_index, correct)
        states = self.store.get_mastery(learner_id)
        current = states.get(question["competency"], MasteryState(question["competency"], difficulty=question["difficulty"]))
        updated = self.mastery_engine.update(current, correct=correct, first_try=(prior_attempts == 0 and correct))
        self.store.save_mastery(learner_id, updated)
        return {
            "correct": correct,
            "advance": correct,
            "explanation": question["explanation"] if correct else "Incorrect. Review the choices and try again.",
            "competency": question["competency"],
            "mastery": round(updated.mastery, 3),
            "difficulty": updated.difficulty,
        }


class AnswerRequest(BaseModel):
    choice_index: int = Field(ge=0, le=3)


def build_service_from_env() -> TutorService:
    required = [
        "SARA_GENERATOR_URL",
        "SARA_GENERATOR_TOKEN",
        "ROAD_VERIFIER_URL",
        "ROAD_VERIFIER_TOKEN",
        "SARA_TUTOR_HMAC_SECRET",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing required configuration: " + ", ".join(missing))
    return TutorService(
        store=Store(os.getenv("SARA_TUTOR_DB_PATH", "/data/sara_tutor.db")),
        sara=SaraQuestionClient(
            os.environ["SARA_GENERATOR_URL"],
            os.environ["SARA_GENERATOR_TOKEN"],
            float(os.getenv("SARA_GENERATOR_TIMEOUT", "20")),
        ),
        road=RoadVerifierClient(
            os.environ["ROAD_VERIFIER_URL"],
            os.environ["ROAD_VERIFIER_TOKEN"],
            float(os.getenv("ROAD_VERIFIER_TIMEOUT", "15")),
        ),
        sealer=AnswerSealer(os.environ["SARA_TUTOR_HMAC_SECRET"].encode()),
        max_generation_attempts=int(os.getenv("SARA_MAX_GENERATION_ATTEMPTS", "8")),
        duplicate_threshold=float(os.getenv("SARA_DUPLICATE_THRESHOLD", "0.72")),
    )


def create_app(service: TutorService | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        if app_instance.state.service is None:
            app_instance.state.service = build_service_from_env()
        yield

    application = FastAPI(
        title="SARA AI Product Manager Adaptive Tutor",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.service = service

    @application.get("/healthz")
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    @application.get("/readyz")
    def readyz() -> dict[str, bool]:
        if application.state.service is None:
            raise HTTPException(503, "service not configured")
        return {"ready": True}

    @application.post("/v1/session/{learner_id}/questions/next")
    async def next_question(learner_id: str) -> dict[str, Any]:
        if len(learner_id) > 200:
            raise HTTPException(400, "learner_id too long")
        try:
            return await application.state.service.next_question(learner_id)
        except (GenerationBlocked, ProviderError) as exc:
            raise HTTPException(503, str(exc)) from exc

    @application.post("/v1/session/{learner_id}/questions/{question_id}/answer")
    def answer(learner_id: str, question_id: str, request: AnswerRequest) -> dict[str, Any]:
        try:
            return application.state.service.answer(learner_id, question_id, request.choice_index)
        except QuestionNotFound as exc:
            raise HTTPException(404, "question not found") from exc
        except QuestionAlreadyCompleted as exc:
            raise HTTPException(409, "question already completed") from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @application.get("/v1/session/{learner_id}/mastery")
    def mastery(learner_id: str) -> dict[str, Any]:
        states = application.state.service.store.get_mastery(learner_id)
        return {
            "learner_id": learner_id,
            "competencies": {name: state.__dict__ for name, state in states.items()},
        }

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "SARA_AI_Product_Manager_Adaptive_Tutor_UNIFIED:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        proxy_headers=True,
    )
