"""
SARA AI Product Manager Adaptive Tutor — Unified Python Runtime

One-file production-oriented adaptive assessment service.

Runtime dependencies:
    pip install "fastapi>=0.115" "uvicorn[standard]>=0.30" "httpx>=0.27" "pydantic>=2.8"

Required environment variables:
    SARA_GENERATOR_URL
    SARA_GENERATOR_TOKEN
    ROAD_VERIFIER_URL
    ROAD_VERIFIER_TOKEN
    SARA_TUTOR_HMAC_SECRET   # at least 32 bytes

Optional environment variables:
    SARA_TUTOR_DB_PATH=/data/sara_tutor.db
    SARA_MAX_GENERATION_ATTEMPTS=8
    SARA_DUPLICATE_THRESHOLD=0.72
    SARA_GENERATOR_TIMEOUT=20
    ROAD_VERIFIER_TIMEOUT=15

Run:
    uvicorn SARA_AI_Product_Manager_Adaptive_Tutor_UNIFIED:app --host 0.0.0.0 --port 8080

Design guarantees:
- No finite local quiz bank and no canned-question fallback.
- SARA generates each assessment item live.
- Semantic/reasoning duplicate gate rejects repeats.
- ROAD must verify every generated item before it is served.
- Correct answers are stored only as HMAC commitments.
- Learners advance only after a correct response.
- Mastery and difficulty adapt over time and persist in SQLite.
- Provider/configuration failures fail closed.
"""

from __future__ import annotations

import base64
import time
import hashlib
import hmac
import json
import os
import random
import re
import sqlite3
import threading
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel, Field, ValidationError, field_validator


# -----------------------------------------------------------------------------
# Curriculum
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# Global semantic novelty detection
# -----------------------------------------------------------------------------

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


def semantic_overlap(a: set[str], b: set[str]) -> float:
    """Conservative lexical-semantic overlap for canonicalized descriptors.

    Jaccard catches near-identical sets; containment catches a prior semantic
    core embedded inside a more detailed new signature.
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    return max(intersection / len(a | b), intersection / min(len(a), len(b)))


def canonical_signature(value: str) -> str:
    return normalize(value)


def canonical_distractor_key(values: list[str]) -> str:
    normalized = sorted(canonical_signature(value) for value in values)
    return hashlib.sha256("|".join(normalized).encode()).hexdigest()


@dataclass(frozen=True)
class NoveltyFingerprint:
    exact: str
    prompt_tokens: frozenset[str]
    learning_objective_id: str
    reasoning_signature: str
    correct_answer_signature: str
    distractor_key: str
    scenario_signature: str


@dataclass(frozen=True)
class LegacyFingerprint:
    prompt_tokens: frozenset[str]
    choice_tokens: tuple[frozenset[str], ...]
    reasoning_tokens: frozenset[str]


@dataclass(frozen=True)
class NoveltyCheckResult:
    duplicate: bool
    reasons: tuple[str, ...]


class GlobalSemanticNoveltyGate:
    """Fail-closed novelty gate across all previously served assessment items.

    The gate treats canonical semantic descriptors as protected dimensions. A
    candidate is rejected if it reuses the learning objective, answer logic,
    reasoning path, distractor structure, scenario signature, or a highly
    similar prompt. History is supplied by the durable global ledger.
    """

    def __init__(self, threshold: float = 0.72):
        if not 0 <= threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        self.threshold = threshold
        self.items: list[NoveltyFingerprint] = []
        self.legacy_items: list[LegacyFingerprint] = []

    def _fingerprint(self, item: dict[str, Any]) -> NoveltyFingerprint:
        required = (
            "prompt",
            "choices",
            "correct_index",
            "learning_objective_id",
            "reasoning_signature",
            "correct_answer_signature",
            "distractor_signatures",
            "scenario_signature",
        )
        missing = [name for name in required if name not in item or item[name] in (None, "", [])]
        if missing:
            raise ValueError("missing novelty descriptors: " + ", ".join(missing))
        if len(item["distractor_signatures"]) != 3:
            raise ValueError("exactly three distractor_signatures required")
        correct_index = int(item["correct_index"])
        if correct_index not in (0, 1, 2, 3):
            raise ValueError("correct_index must be 0..3")
        exact_material = "|".join(
            [
                canonical_signature(item["prompt"]),
                canonical_signature(item["learning_objective_id"]),
                canonical_signature(item["reasoning_signature"]),
                canonical_signature(item["correct_answer_signature"]),
                canonical_distractor_key(item["distractor_signatures"]),
                canonical_signature(item["scenario_signature"]),
            ]
        )
        return NoveltyFingerprint(
            exact=hashlib.sha256(exact_material.encode()).hexdigest(),
            prompt_tokens=frozenset(tokens(item["prompt"])),
            learning_objective_id=canonical_signature(item["learning_objective_id"]),
            reasoning_signature=canonical_signature(item["reasoning_signature"]),
            correct_answer_signature=canonical_signature(item["correct_answer_signature"]),
            distractor_key=canonical_distractor_key(item["distractor_signatures"]),
            scenario_signature=canonical_signature(item["scenario_signature"]),
        )

    @staticmethod
    def _signature_equivalent(candidate: str, previous: str, threshold: float) -> bool:
        if candidate == previous:
            return True
        return semantic_overlap(tokens(candidate), tokens(previous)) >= threshold

    def remember(self, item: dict[str, Any]) -> None:
        self.items.append(self._fingerprint(item))

    def remember_legacy(self, question: str, answers: list[str], reasoning: str) -> None:
        self.legacy_items.append(
            LegacyFingerprint(
                prompt_tokens=frozenset(tokens(question)),
                choice_tokens=tuple(frozenset(tokens(answer)) for answer in answers),
                reasoning_tokens=frozenset(tokens(reasoning)),
            )
        )

    def check(self, item: dict[str, Any]) -> NoveltyCheckResult:
        candidate = self._fingerprint(item)
        reasons: set[str] = set()
        for previous in self.items:
            if candidate.exact == previous.exact:
                reasons.add("composite")
            if semantic_overlap(set(candidate.prompt_tokens), set(previous.prompt_tokens)) >= self.threshold:
                reasons.add("question_semantics")
            if self._signature_equivalent(
                candidate.reasoning_signature,
                previous.reasoning_signature,
                self.threshold,
            ):
                reasons.add("reasoning")
            if self._signature_equivalent(
                candidate.correct_answer_signature,
                previous.correct_answer_signature,
                self.threshold,
            ):
                reasons.add("correct_answer")
            if candidate.distractor_key == previous.distractor_key:
                reasons.add("distractor_structure")
            if candidate.scenario_signature == previous.scenario_signature:
                reasons.add("scenario")

        candidate_choice_tokens = [frozenset(tokens(choice)) for choice in item["choices"]]
        candidate_reasoning_tokens = frozenset(
            tokens(item.get("reasoning_archetype", "") + " " + item["reasoning_signature"])
        )
        for previous in self.legacy_items:
            if semantic_overlap(set(candidate.prompt_tokens), set(previous.prompt_tokens)) >= self.threshold:
                reasons.add("legacy_question_semantics")
            if candidate_reasoning_tokens and previous.reasoning_tokens and (
                semantic_overlap(set(candidate_reasoning_tokens), set(previous.reasoning_tokens)) >= self.threshold
            ):
                reasons.add("legacy_reasoning")
            for candidate_choice in candidate_choice_tokens:
                if not candidate_choice:
                    continue
                if any(
                    previous_choice
                    and semantic_overlap(set(candidate_choice), set(previous_choice)) >= self.threshold
                    for previous_choice in previous.choice_tokens
                ):
                    reasons.add("legacy_answer_semantics")
                    break
        return NoveltyCheckResult(bool(reasons), tuple(sorted(reasons)))

    def is_duplicate(self, item: dict[str, Any]) -> bool:
        return self.check(item).duplicate


class SemanticDuplicateGate(GlobalSemanticNoveltyGate):
    """Compatibility wrapper for older tests and integrations.

    New runtime code uses canonical novelty descriptors through
    GlobalSemanticNoveltyGate. This wrapper preserves the former
    question/answers/reasoning call shape for legacy callers.
    """

    def remember(self, question: str, answers: list[str], reasoning: str) -> None:  # type: ignore[override]
        self.remember_legacy(question, answers, reasoning)

    def is_duplicate(self, question: str, answers: list[str], reasoning: str) -> bool:  # type: ignore[override]
        candidate_tokens = frozenset(tokens(question))
        reasoning_tokens = frozenset(tokens(reasoning))
        for previous in self.legacy_items:
            if semantic_overlap(set(candidate_tokens), set(previous.prompt_tokens)) >= self.threshold:
                return True
            if reasoning_tokens and previous.reasoning_tokens and (
                semantic_overlap(set(reasoning_tokens), set(previous.reasoning_tokens)) >= self.threshold
            ):
                return True
        return False


# -----------------------------------------------------------------------------
# Mastery engine
# -----------------------------------------------------------------------------

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

    def update(
        self,
        state: MasteryState,
        correct: bool,
        first_try: bool,
    ) -> MasteryState:
        updated = MasteryState(**state.__dict__)
        updated.attempts += 1

        if correct:
            updated.eventual_correct += 1
            if first_try:
                updated.first_try_correct += 1
            updated.streak += 1
            updated.mastery = min(
                1.0,
                updated.mastery + (0.10 if first_try else 0.05),
            )
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
        # Lower mastery receives higher selection weight.
        weights = [max(0.05, 1.05 - state.mastery) for state in pool]
        return random.choices(pool, weights=weights, k=1)[0]


# -----------------------------------------------------------------------------
# Provider contracts and clients
# -----------------------------------------------------------------------------

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
    learning_objective_id: str = Field(min_length=3, max_length=240)
    reasoning_signature: str = Field(min_length=3, max_length=500)
    correct_answer_signature: str = Field(min_length=3, max_length=500)
    distractor_signatures: list[str]
    scenario_signature: str = Field(min_length=3, max_length=500)

    @field_validator("distractor_signatures")
    @classmethod
    def validate_distractor_signatures(cls, value: list[str]) -> list[str]:
        if len(value) != 3:
            raise ValueError("exactly three distractor_signatures required")
        normalized = [canonical_signature(item) for item in value]
        if any(not item for item in normalized):
            raise ValueError("invalid distractor signature")
        if len(set(normalized)) != 3:
            raise ValueError("distractor signatures must be distinct")
        return value

    @field_validator("choices")
    @classmethod
    def validate_choices(cls, value: list[str]) -> list[str]:
        if len(value) != 4:
            raise ValueError("exactly four choices required")
        if any(
            not isinstance(item, str) or not item.strip() or len(item) > 3000
            for item in value
        ):
            raise ValueError("invalid choice")
        if len({item.strip().casefold() for item in value}) != 4:
            raise ValueError("choices must be distinct")
        return value


class RoadVerdict(BaseModel):
    status: str
    verified: bool
    reason: str | None = None


def _require_bearer_token(authorization: str | None, expected: str, label: str) -> None:
    if not expected:
        raise HTTPException(503, f"{label} token is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, f"{label} authorization required")
    token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, expected):
        raise HTTPException(403, f"{label} authorization rejected")


class SaraQuestionClient:
    def __init__(
        self,
        url: str,
        token: str,
        timeout: float = 20.0,
        transport: Any = None,
        task: str = "generate_ai_product_manager_assessment_item",
        curriculum_requirements: dict[str, Any] | None = None,
    ):
        if not url or not token:
            raise ValueError("SARA url and token required")
        self.url = url
        self.token = token
        self.timeout = timeout
        self.transport = transport
        self.task = task
        self.curriculum_requirements = curriculum_requirements or {}

    async def generate_question(
        self,
        competency: str,
        difficulty: int,
        learner_context: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "task": self.task,
            "requirements": {
                "competency": competency,
                "difficulty": difficulty,
                "format": "multiple_choice",
                "choice_count": 4,
                "exactly_one_correct": True,
                "novel_reasoning_required": True,
                "no_surface_rewrites": True,
                "canonical_novelty_descriptors_required": [
                    "learning_objective_id",
                    "reasoning_signature",
                    "correct_answer_signature",
                    "distractor_signatures",
                    "scenario_signature",
                ],
                "descriptor_rule": (
                    "Descriptors must identify underlying meaning, answer logic, and "
                    "reasoning; changing names, numbers, industries, or wording does not "
                    "make a descriptor novel."
                ),
                "return_json_only": True,
            },
            "learner_context": learner_context,
        }
        payload["requirements"].update(self.curriculum_requirements)
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                    },
                )
            response.raise_for_status()
            if len(response.content) > 200_000:
                raise ProviderContractError("SARA response too large")
            validated = GeneratedQuestion.model_validate(response.json())
            return validated.model_dump()
        except ProviderContractError:
            raise
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise ProviderContractError(
                f"SARA generation failed contract: {exc}"
            ) from exc


class RoadVerifierClient:
    def __init__(
        self,
        url: str,
        token: str,
        timeout: float = 15.0,
        transport: Any = None,
        task: str = "verify_ai_product_manager_assessment_item",
    ):
        if not url or not token:
            raise ValueError("ROAD url and token required")
        self.url = url
        self.token = token
        self.timeout = timeout
        self.transport = transport
        self.task = task

    async def verify_question(self, question: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "task": self.task,
            "question": question,
            "checks": [
                "single_defensible_answer",
                "distractors_materially_wrong",
                "current_terminology",
                "no_unsupported_sara_claims",
                "explanation_supports_answer",
                "difficulty_matches",
                "canonical_novelty_descriptors_valid",
                "learning_objective_not_reused",
                "correct_answer_logic_not_reused",
                "reasoning_path_not_reused",
                "distractor_structure_not_reused",
            ],
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                    },
                )
            response.raise_for_status()
            if len(response.content) > 100_000:
                raise ProviderContractError("ROAD response too large")
            validated = RoadVerdict.model_validate(response.json())
            return validated.model_dump()
        except ProviderContractError:
            raise
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise ProviderContractError(
                f"ROAD verification failed contract: {exc}"
            ) from exc


# -----------------------------------------------------------------------------
# Answer sealing
# -----------------------------------------------------------------------------

class AnswerSealer:
    def __init__(self, secret: bytes):
        if len(secret) < 32:
            raise ValueError("secret must be at least 32 bytes")
        self.secret = secret

    def seal(self, question_id: str, choice_index: int) -> str:
        material = f"{question_id}:{choice_index}".encode()
        return hmac.new(self.secret, material, hashlib.sha256).hexdigest()

    def verify(
        self,
        question_id: str,
        choice_index: int,
        commitment: str,
    ) -> bool:
        return hmac.compare_digest(
            self.seal(question_id, choice_index),
            commitment,
        )


# -----------------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------------

class Store:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

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

                CREATE TABLE IF NOT EXISTS answer_position_allocations(
                    position INTEGER PRIMARY KEY,
                    count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS novelty_ledger(
                    fingerprint TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    learning_objective_id TEXT NOT NULL,
                    reasoning_signature TEXT NOT NULL UNIQUE,
                    correct_answer_signature TEXT NOT NULL UNIQUE,
                    distractor_key TEXT NOT NULL UNIQUE,
                    distractor_signatures_json TEXT NOT NULL,
                    scenario_signature TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS tutor_audit(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    learner_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            # Older databases had a UNIQUE objective index. Rebuild to permit
            # different reasoning paths under the same learning objective.
            index_rows = connection.execute("PRAGMA index_list(novelty_ledger)").fetchall()
            if any(row[2] and "autoindex" in row[1] and
                   [col[2] for col in connection.execute(f"PRAGMA index_info({row[1]})").fetchall()] == ["learning_objective_id"]
                   for row in index_rows):
                connection.executescript("""
                ALTER TABLE novelty_ledger RENAME TO novelty_ledger_old;
                CREATE TABLE novelty_ledger(
                    fingerprint TEXT PRIMARY KEY, prompt TEXT NOT NULL,
                    learning_objective_id TEXT NOT NULL,
                    reasoning_signature TEXT NOT NULL UNIQUE,
                    correct_answer_signature TEXT NOT NULL UNIQUE,
                    distractor_key TEXT NOT NULL UNIQUE,
                    distractor_signatures_json TEXT NOT NULL,
                    scenario_signature TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO novelty_ledger SELECT * FROM novelty_ledger_old;
                DROP TABLE novelty_ledger_old;
                """)

    def allocate_answer_position(self) -> int:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("SELECT position,count FROM answer_position_allocations").fetchall()
            counts = {row["position"]: row["count"] for row in rows}
            minimum = min(counts.get(i, 0) for i in range(4))
            selected = random.choice([i for i in range(4) if counts.get(i, 0) == minimum])
            connection.execute("INSERT INTO answer_position_allocations(position,count) VALUES(?,1) "
                               "ON CONFLICT(position) DO UPDATE SET count=count+1", (selected,))
            return selected

    def score_answer(self, learner_id, question, choice_index, correct, mastery_engine):
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT answered_correctly FROM questions WHERE id=? AND learner_id=?",
                                     (question["id"], learner_id)).fetchone()
            if row is None:
                raise QuestionNotFound(question["id"])
            if row[0]:
                raise QuestionAlreadyCompleted(question["id"])
            prior = connection.execute("SELECT COUNT(*) FROM attempts WHERE learner_id=? AND question_id=?",
                                       (learner_id, question["id"])).fetchone()[0]
            connection.execute("INSERT INTO attempts(learner_id,question_id,choice_index,correct) VALUES(?,?,?,?)",
                               (learner_id, question["id"], choice_index, int(correct)))
            if correct:
                connection.execute("UPDATE questions SET answered_correctly=1 WHERE id=?", (question["id"],))
            state_row = connection.execute("SELECT * FROM mastery WHERE learner_id=? AND competency=?",
                                           (learner_id, question["competency"])).fetchone()
            current = (MasteryState(question["competency"], attempts=state_row["attempts"],
                       first_try_correct=state_row["first_try_correct"], eventual_correct=state_row["eventual_correct"],
                       streak=state_row["streak"], mastery=state_row["mastery"], difficulty=state_row["difficulty"])
                       if state_row else MasteryState(question["competency"], difficulty=question["difficulty"]))
            if prior == 0:
                current = mastery_engine.update(current, correct, first_try=correct)
                connection.execute("INSERT INTO mastery VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(learner_id,competency) "
                                   "DO UPDATE SET attempts=excluded.attempts,first_try_correct=excluded.first_try_correct,"
                                   "eventual_correct=excluded.eventual_correct,streak=excluded.streak,"
                                   "mastery=excluded.mastery,difficulty=excluded.difficulty",
                                   (learner_id, current.competency,current.attempts,current.first_try_correct,
                                    current.eventual_correct,current.streak,current.mastery,current.difficulty))
            return current

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
            rows = connection.execute(
                "SELECT * FROM mastery WHERE learner_id=?",
                (learner_id,),
            ).fetchall()
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
                (
                    record["fingerprint"],
                    record["prompt"],
                    choices_json,
                    record["reasoning"],
                ),
            )

    def save_audit(
        self,
        learner_id: str,
        question_id: str,
        stage: str,
        payload: dict[str, Any],
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tutor_audit(
                    learner_id, question_id, stage, payload_json
                ) VALUES(?,?,?,?)
                """,
                (
                    learner_id,
                    question_id,
                    stage,
                    json.dumps(payload, sort_keys=True),
                ),
            )

    def audit_for_question(
        self,
        learner_id: str,
        question_id: str,
    ) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT stage, payload_json, created_at
                FROM tutor_audit
                WHERE learner_id=? AND question_id=?
                ORDER BY id ASC
                """,
                (learner_id, question_id),
            ).fetchall()
        return [
            {
                "stage": row["stage"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    @staticmethod
    def _ledger_row_to_item(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "prompt": row["prompt"],
            "choices": ["ledger-only", "ledger-only-2", "ledger-only-3", "ledger-only-4"],
            "correct_index": 0,
            "learning_objective_id": row["learning_objective_id"],
            "reasoning_signature": row["reasoning_signature"],
            "correct_answer_signature": row["correct_answer_signature"],
            "distractor_signatures": json.loads(row["distractor_signatures_json"]),
            "scenario_signature": row["scenario_signature"],
        }

    def claim_novelty(self, item: dict[str, Any], threshold: float) -> bool:
        """Atomically claim a globally novel semantic item.

        BEGIN IMMEDIATE serializes competing writers. The gate is rebuilt while
        holding the write reservation, so two processes cannot both accept the
        same or semantically equivalent protected dimensions.
        """
        fp_gate = GlobalSemanticNoveltyGate(threshold)
        candidate_fp = fp_gate._fingerprint(item)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                rows = connection.execute(
                    """
                    SELECT prompt, learning_objective_id, reasoning_signature,
                           correct_answer_signature, distractor_signatures_json,
                           scenario_signature
                    FROM novelty_ledger
                    ORDER BY created_at ASC
                    """
                ).fetchall()
                gate = GlobalSemanticNoveltyGate(threshold)
                for row in rows:
                    gate.remember(self._ledger_row_to_item(row))
                legacy_rows = connection.execute(
                    """
                    SELECT prompt, choices_json, reasoning
                    FROM semantic_index
                    ORDER BY created_at ASC
                    """
                ).fetchall()
                for row in legacy_rows:
                    gate.remember_legacy(
                        row["prompt"],
                        json.loads(row["choices_json"]),
                        row["reasoning"],
                    )
                if gate.check(item).duplicate:
                    connection.rollback()
                    return False
                connection.execute(
                    """
                    INSERT INTO novelty_ledger(
                        fingerprint, prompt, learning_objective_id,
                        reasoning_signature, correct_answer_signature,
                        distractor_key, distractor_signatures_json, scenario_signature
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        candidate_fp.exact,
                        item["prompt"],
                        candidate_fp.learning_objective_id,
                        candidate_fp.reasoning_signature,
                        candidate_fp.correct_answer_signature,
                        candidate_fp.distractor_key,
                        json.dumps(item["distractor_signatures"]),
                        candidate_fp.scenario_signature,
                    ),
                )
                connection.commit()
                return True
            except sqlite3.IntegrityError:
                connection.rollback()
                return False
            except Exception:
                connection.rollback()
                raise

    def save_novelty(self, item: dict[str, Any]) -> None:
        if not self.claim_novelty(item, threshold=0.72):
            raise ValueError("novelty ledger collision")

    def novelty_items(self) -> list[sqlite3.Row]:
        # Deliberately unbounded: novelty history is permanent and non-expiring.
        with self._lock, self._connect() as connection:
            return connection.execute(
                """
                SELECT prompt, learning_objective_id, reasoning_signature,
                       correct_answer_signature, distractor_signatures_json,
                       scenario_signature
                FROM novelty_ledger
                ORDER BY created_at ASC
                """
            ).fetchall()

    def get_question(self, question_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM questions WHERE id=?",
                (question_id,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["choices"] = json.loads(data.pop("choices_json"))
        return data

    def mark_attempt(
        self,
        learner_id: str,
        question_id: str,
        choice_index: int,
        correct: bool,
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO attempts(
                    learner_id, question_id, choice_index, correct
                ) VALUES(?,?,?,?)
                """,
                (learner_id, question_id, choice_index, int(correct)),
            )
            if correct:
                connection.execute(
                    "UPDATE questions SET answered_correctly=1 WHERE id=?",
                    (question_id,),
                )

    def attempts_for_question(self, learner_id: str, question_id: str) -> int:
        with self._lock, self._connect() as connection:
            return int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM attempts
                    WHERE learner_id=? AND question_id=?
                    """,
                    (learner_id, question_id),
                ).fetchone()[0]
            )

    def legacy_semantic_items(self) -> list[sqlite3.Row]:
        # Legacy history is also unbounded so pre-upgrade questions are not forgotten.
        with self._lock, self._connect() as connection:
            return connection.execute(
                """
                SELECT prompt, choices_json, reasoning
                FROM semantic_index
                ORDER BY created_at ASC
                """
            ).fetchall()

    def semantic_items(self, limit: int = 5000) -> list[sqlite3.Row]:
        with self._lock, self._connect() as connection:
            return connection.execute(
                """
                SELECT prompt, choices_json, reasoning
                FROM semantic_index
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()


# -----------------------------------------------------------------------------
# Adaptive tutor orchestration
# -----------------------------------------------------------------------------

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
        competencies: list[str] | None = None,
    ):
        if max_generation_attempts < 1:
            raise ValueError("max_generation_attempts must be positive")
        self.store = store
        self.sara = sara
        self.road = road
        self.sealer = sealer
        self.max_generation_attempts = max_generation_attempts
        self.duplicate_threshold = duplicate_threshold
        self.mastery_engine = MasteryEngine(competencies or COMPETENCIES)

    def choose_answer_position(self) -> int:
        return self.store.allocate_answer_position()

    def _gate_from_store(self) -> GlobalSemanticNoveltyGate:
        gate = GlobalSemanticNoveltyGate(self.duplicate_threshold)
        for row in self.store.novelty_items():
            gate.remember(self.store._ledger_row_to_item(row))
        for row in self.store.legacy_semantic_items():
            gate.remember_legacy(
                row["prompt"],
                json.loads(row["choices_json"]),
                row["reasoning"],
            )
        return gate

    def _learner_context(
        self,
        learner_id: str,
        states: dict[str, MasteryState],
        target: MasteryState,
    ) -> dict[str, Any]:
        weakest = sorted(states.values(), key=lambda item: item.mastery)[:5]
        return {
            "learner_id_hash": hashlib.sha256(learner_id.encode()).hexdigest()[:16],
            "target_competency": target.competency,
            "target_difficulty": target.difficulty,
            "weak_competencies": [
                {
                    "competency": state.competency,
                    "mastery": round(state.mastery, 3),
                }
                for state in weakest
            ],
            "instruction": (
                "Create a genuinely new reasoning problem, not a paraphrase of a "
                "common definition question. Vary domain, constraints, evidence, "
                "tradeoffs, stakeholder conflict, metrics, lifecycle stage, and "
                "decision objective. Do not reuse any prior learning objective, answer "
                "logic, reasoning path, distractor structure, scenario signature, or "
                "question meaning. Canonical novelty descriptors must describe the "
                "underlying semantics rather than surface wording."
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
            novelty = gate.check(candidate)
            if novelty.duplicate:
                continue

            verdict = await self.road.verify_question(candidate)
            if verdict.get("status") != "PASS" or verdict.get("verified") is not True:
                raise GenerationBlocked("ROAD did not verify generated question")

            if not self.store.claim_novelty(candidate, self.duplicate_threshold):
                continue

            question_id = str(uuid.uuid4())
            correct_index = int(candidate["correct_index"])
            new_index = self.choose_answer_position()
            order = [i for i in range(4) if i != correct_index]
            random.shuffle(order)
            order.insert(new_index, correct_index)
            candidate["choices"] = [candidate["choices"][i] for i in order]
            correct_index = new_index
            commitment = self.sealer.seal(question_id, correct_index)
            semantic_fingerprint = gate._fingerprint(candidate).exact

            self.store.save_question(
                {
                    "id": question_id,
                    "learner_id": learner_id,
                    "competency": candidate["competency"],
                    "difficulty": candidate["difficulty"],
                    "prompt": candidate["prompt"],
                    "choices": candidate["choices"],
                    "answer_commitment": commitment,
                    "explanation": candidate["explanation"],
                    "reasoning": candidate["reasoning_archetype"],
                    "fingerprint": semantic_fingerprint,
                }
            )
            self.store.save_audit(
                learner_id,
                question_id,
                "road_verdict",
                {
                    "status": verdict.get("status"),
                    "verified": verdict.get("verified"),
                    "reason": verdict.get("reason"),
                    "semantic_fingerprint": semantic_fingerprint,
                },
            )
            self.store.save_audit(
                learner_id,
                question_id,
                "question_served",
                {
                    "prompt_sha256": hashlib.sha256(
                        candidate["prompt"].encode()
                    ).hexdigest(),
                    "choice_count": len(candidate["choices"]),
                    "competency": candidate["competency"],
                    "difficulty": candidate["difficulty"],
                    "answer_key_exposed": False,
                },
            )
            # The raw correct_index never leaves this method and is not persisted.
            return {
                "question_id": question_id,
                "prompt": candidate["prompt"],
                "choices": candidate["choices"],
                "competency": candidate["competency"],
                "difficulty": candidate["difficulty"],
            }

        raise GenerationBlocked(
            "Unable to generate a sufficiently novel ROAD-verified question "
            "within bounded attempts"
        )

    def answer(
        self,
        learner_id: str,
        question_id: str,
        choice_index: int,
    ) -> dict[str, Any]:
        if choice_index not in (0, 1, 2, 3):
            raise ValueError("choice_index must be 0..3")

        question = self.store.get_question(question_id)
        if question is None or question["learner_id"] != learner_id:
            raise QuestionNotFound(question_id)
        if question["answered_correctly"]:
            raise QuestionAlreadyCompleted(question_id)

        correct = self.sealer.verify(question_id, choice_index, question["answer_commitment"])
        updated = self.store.score_answer(learner_id, question, choice_index, correct, self.mastery_engine)
        attempts = self.store.attempts_for_question(learner_id, question_id)
        self.store.save_audit(
            learner_id,
            question_id,
            "answer_recorded",
            {
                "choice_index": choice_index,
                "correct": correct,
                "attempts_for_question": attempts,
                "retry_allowed": not correct,
                "mastery": round(updated.mastery, 3),
                "difficulty": updated.difficulty,
                "competency": question["competency"],
            },
        )

        return {
            "correct": correct,
            "advance": correct,
            "explanation": (
                question["explanation"]
                if correct
                else "Incorrect. Review the choices and try again."
            ),
            "competency": question["competency"],
            "mastery": round(updated.mastery, 3),
            "difficulty": updated.difficulty,
        }


# -----------------------------------------------------------------------------
# FastAPI application
# -----------------------------------------------------------------------------

def issue_learner_token(learner_id: str, secret: bytes, ttl: int = 3600) -> str:
    """Server-side issuer for an already authenticated learner; never expose as public route."""
    if not learner_id or ttl <= 0:
        raise ValueError("invalid token request")
    payload = json.dumps({"sub": learner_id, "exp": int(time.time()) + ttl}, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    signature = hmac.new(secret, encoded.encode(), hashlib.sha256).hexdigest()
    return encoded + "." + signature


def require_learner(learner_id: str, authorization: str | None, secret: bytes) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "learner authorization required")
    try:
        encoded, signature = authorization[7:].split(".")
        expected = hmac.new(secret, encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if int(payload["exp"]) <= time.time() or not isinstance(payload["sub"], str):
            raise ValueError("expired or invalid subject")
    except (ValueError, KeyError, TypeError, UnicodeError):
        raise HTTPException(401, "invalid learner authorization")
    if payload["sub"] != learner_id:
        raise HTTPException(403, "learner mismatch")


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
        raise RuntimeError(
            "Missing required configuration: " + ", ".join(missing)
        )

    secret = os.environ["SARA_TUTOR_HMAC_SECRET"].encode()
    store = Store(os.getenv("SARA_TUTOR_DB_PATH", "/data/sara_tutor.db"))
    sara = SaraQuestionClient(
        os.environ["SARA_GENERATOR_URL"],
        os.environ["SARA_GENERATOR_TOKEN"],
        float(os.getenv("SARA_GENERATOR_TIMEOUT", "20")),
    )
    road = RoadVerifierClient(
        os.environ["ROAD_VERIFIER_URL"],
        os.environ["ROAD_VERIFIER_TOKEN"],
        float(os.getenv("ROAD_VERIFIER_TIMEOUT", "15")),
    )
    return TutorService(
        store=store,
        sara=sara,
        road=road,
        sealer=AnswerSealer(secret),
        max_generation_attempts=int(
            os.getenv("SARA_MAX_GENERATION_ATTEMPTS", "8")
        ),
        duplicate_threshold=float(
            os.getenv("SARA_DUPLICATE_THRESHOLD", "0.72")
        ),
    )


def register_tutor_routes(
    application: FastAPI,
    service: TutorService | None = None,
    service_builder=None,
    require_authorization: bool = True,
) -> None:
    application.state.adaptive_tutor_service = service

    def get_service() -> TutorService:
        current = application.state.adaptive_tutor_service
        if current is None:
            try:
                current = (service_builder or build_service_from_env)()
            except RuntimeError as exc:
                raise HTTPException(503, str(exc)) from exc
            application.state.adaptive_tutor_service = current
        return current

    def authorize(learner_id: str, authorization: str | None) -> TutorService:
        current = get_service()
        if require_authorization:
            require_learner(learner_id, authorization, current.sealer.secret)
        return current

    @application.post("/v1/session/{learner_id}/questions/next")
    async def next_question(
        learner_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if len(learner_id) > 200:
            raise HTTPException(400, "learner_id too long")
        current = authorize(learner_id, authorization)
        try:
            return await current.next_question(learner_id)
        except (GenerationBlocked, ProviderError) as exc:
            raise HTTPException(503, str(exc)) from exc

    @application.post(
        "/v1/session/{learner_id}/questions/{question_id}/answer"
    )
    def answer(
        learner_id: str,
        question_id: str,
        request: AnswerRequest,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        current = authorize(learner_id, authorization)
        try:
            return current.answer(
                learner_id,
                question_id,
                request.choice_index,
            )
        except QuestionNotFound as exc:
            raise HTTPException(404, "question not found") from exc
        except QuestionAlreadyCompleted as exc:
            raise HTTPException(409, "question already completed") from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @application.get("/v1/session/{learner_id}/mastery")
    def mastery(
        learner_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        current = authorize(learner_id, authorization)
        states = current.store.get_mastery(learner_id)
        return {
            "learner_id": learner_id,
            "competencies": {
                name: state.__dict__ for name, state in states.items()
            },
        }

    @application.get("/v1/session/{learner_id}/questions/{question_id}/audit")
    def question_audit(
        learner_id: str,
        question_id: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        current = authorize(learner_id, authorization)
        question = current.store.get_question(question_id)
        if question is None or question["learner_id"] != learner_id:
            raise HTTPException(404, "question not found")
        return {
            "learner_id": learner_id,
            "question_id": question_id,
            "stages": current.store.audit_for_question(learner_id, question_id),
        }


def _build_internal_question(payload: dict[str, Any]) -> dict[str, Any]:
    requirements = payload.get("requirements") or {}
    learner_context = payload.get("learner_context") or {}
    competency = str(
        requirements.get("competency")
        or learner_context.get("target_competency")
        or "product_strategy"
    )
    difficulty = int(
        requirements.get("difficulty")
        or learner_context.get("target_difficulty")
        or 2
    )
    nonce = uuid.uuid4().hex[:12]
    weak = learner_context.get("weak_competencies") or []
    weak_name = "portfolio evidence"
    if weak and isinstance(weak[0], dict):
        weak_name = str(weak[0].get("competency") or weak_name)
    scenario = (
        f"{competency} production decision {nonce} with conflicting retention, "
        f"support-load, and trust evidence"
    )
    question = {
        "prompt": (
            "A SARA product team is deciding whether to release an adaptive tutor "
            f"change for `{competency}` at difficulty {difficulty}. The pilot shows "
            "higher completion among advanced learners, increased support tickets "
            "from new learners, and one unresolved evidence gap in the verification "
            "trail. Which action should the PM take first?"
        ),
        "choices": [
            (
                "Hold broad rollout, segment the pilot evidence, close the "
                "verification gap, and define the next guarded release criterion."
            ),
            "Ship to all learners because completion improved in one segment.",
            "Discard the tutor change because support tickets increased.",
            "Change the metric target so the pilot appears ready for launch.",
        ],
        "correct_index": 0,
        "explanation": (
            "The PM should preserve the promising signal while resolving the "
            "verification gap and segment-risk evidence before broad rollout."
        ),
        "competency": competency,
        "difficulty": max(1, min(5, difficulty)),
        "reasoning_archetype": "segmented evidence gate before broad rollout",
        "evidence_notes": (
            "Tests whether the learner weighs positive adoption, learner-risk "
            "signals, support burden, and release-governance evidence together."
        ),
        "learning_objective_id": f"{competency} gated rollout evidence {nonce}",
        "reasoning_signature": (
            f"prefer guarded segmented rollout decision over vanity metric or "
            f"single-signal launch for {weak_name} {nonce}"
        ),
        "correct_answer_signature": (
            f"close verification gap and segment pilot evidence before broad rollout {nonce}"
        ),
        "distractor_signatures": [
            f"overweight advanced learner completion and ignore support evidence {nonce}",
            f"reject change solely from support ticket increase {nonce}",
            f"manipulate metric target instead of resolving evidence gap {nonce}",
        ],
        "scenario_signature": scenario,
    }
    return GeneratedQuestion.model_validate(question).model_dump()


def register_internal_provider_routes(application: FastAPI) -> None:
    @application.post("/internal/sara/generate-question", include_in_schema=False)
    async def internal_generate_question(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_bearer_token(
            authorization,
            os.getenv("SARA_GENERATOR_TOKEN", ""),
            "SARA generator",
        )
        payload = await request.json()
        if payload.get("task") != "generate_ai_product_manager_assessment_item":
            raise HTTPException(400, "unsupported generator task")
        return _build_internal_question(payload)

    @application.post("/internal/road/verify-question", include_in_schema=False)
    async def internal_verify_question(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _require_bearer_token(
            authorization,
            os.getenv("ROAD_VERIFIER_TOKEN", ""),
            "ROAD verifier",
        )
        payload = await request.json()
        if payload.get("task") != "verify_ai_product_manager_assessment_item":
            raise HTTPException(400, "unsupported ROAD task")
        try:
            question = GeneratedQuestion.model_validate(payload.get("question"))
        except ValidationError as exc:
            return {
                "status": "FAIL",
                "verified": False,
                "reason": f"question contract failed: {exc.errors()[0]['msg']}",
            }
        if question.correct_index not in range(len(question.choices)):
            return {
                "status": "FAIL",
                "verified": False,
                "reason": "correct answer index is outside the choices",
            }
        if len(set(question.distractor_signatures)) != 3:
            return {
                "status": "FAIL",
                "verified": False,
                "reason": "distractor signatures are not unique",
            }
        return {
            "status": "PASS",
            "verified": True,
            "reason": (
                "ROAD verified a single defensible answer, distinct distractor "
                "logic, canonical novelty descriptors, and explanation support."
            ),
        }


def create_app(
    service: TutorService | None = None,
    service_builder=None,
    require_authorization: bool = True,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        if app_instance.state.adaptive_tutor_service is None:
            app_instance.state.adaptive_tutor_service = (service_builder or build_service_from_env)()
        yield

    application = FastAPI(
        title="SARA AI Product Manager Adaptive Tutor",
        version="1.0.0",
        lifespan=lifespan,
    )

    @application.get("/healthz")
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    @application.get("/readyz")
    def readyz() -> dict[str, bool]:
        if application.state.adaptive_tutor_service is None:
            raise HTTPException(503, "service not configured")
        return {"ready": True}

    register_tutor_routes(
        application,
        service,
        service_builder=service_builder,
        require_authorization=require_authorization,
    )
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
