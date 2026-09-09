from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

ATS_PROFILE_VERSION = "2026-09-08.3"
MODULE_NAME = "sara-ats-intelligence"
BASELINE_CHECKED_AT = datetime(2026, 9, 8, 19, 0, 0, tzinfo=timezone.utc)

Provider = Literal[
    "workday",
    "greenhouse",
    "smartrecruiters",
    "successfactors",
    "taleo",
    "icims",
    "lever",
    "ashby",
    "eightfold",
    "phenom",
    "paradox",
    "unknown",
]
EvidenceState = Literal["VERIFIED", "SUPPORTED", "UNVERIFIED"]
ResumeLane = Literal["AI_PLATFORM_AGENTIC", "AI_GOVERNANCE_CYBERSECURITY", "ENTERPRISE_SUPPORT"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _utcnow()).isoformat()


def _data_dir() -> Path:
    root = Path(os.getenv("SARA_DATA_DIR", "data")).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _normalized_domain(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("evidence/application URL must use HTTPS without embedded credentials")
    return parsed.hostname.lower().rstrip(".")


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9+#./-]+", " ", (text or "").casefold()).strip()


COMMON_FORMAT_RULES = [
    "single-column layout",
    "standard section headings",
    "text-based DOCX preferred",
    "no graphics, icons, text boxes, or decorative skill bars",
    "avoid tables when they can alter parse order",
    "explicit employer, title, and employment dates",
    "explicit education fields where applicable",
    "consistent titles and dates between resume and application profile",
    "role-specific supported skills in context, not hidden keyword stuffing",
]

PROFILES: dict[str, dict[str, Any]] = {
    "workday": {
        "display": "Workday Recruiting",
        "domains": ["myworkdayjobs.com", "myworkdaysite.com", "workday.com"],
        "format_rules": COMMON_FORMAT_RULES + [
            "do not use image-based resume styles",
            "repeat important supported skills in experience context because resume parsing does not auto-fill the Skills field",
            "prioritize required supported skills because Candidate Skills Match gives greater weight to required requisition skills",
        ],
        "evidence": [
            "https://doc.workday.com/admin-guide/en-us/human-capital-management/recruiting/candidates/set-up-prospects-and-candidates/hdc1552497830785.html",
            "https://doc.workday.com/admin-guide/en-us/human-capital-management/recruiting/candidates/candidate-skills-match/bmj1604095304483.html",
        ],
    },
    "greenhouse": {
        "display": "Greenhouse",
        "domains": ["greenhouse.io"],
        "format_rules": COMMON_FORMAT_RULES + [
            "make supported skills and experience easy to compare against the requisition",
            "preserve structured chronology and direct evidence of each claimed competency",
        ],
        "evidence": ["https://www.greenhouse.com/"],
    },
    "smartrecruiters": {
        "display": "SmartRecruiters / Winston Match",
        "domains": ["smartrecruiters.com"],
        "format_rules": COMMON_FORMAT_RULES + [
            "keep candidate-verified experience and education consistent with the resume",
            "do not rely on resume parsing to override verified profile data",
        ],
        "evidence": [
            "https://www.smartrecruiters.com/resources/article/june-2026-product-release-highlights-more-control-confidence-in-hiring-workflows/"
        ],
    },
    "successfactors": {
        "display": "SAP SuccessFactors Recruiting",
        "domains": ["successfactors.com", "successfactors.eu", "jobs.sap.com"],
        "format_rules": COMMON_FORMAT_RULES + [
            "make standard candidate-profile fields explicit",
            "verify parsed candidate profile fields after upload because the profile is separately searchable",
            "keep work experience and education consistent with structured candidate-profile data",
        ],
        "evidence": [
            "https://help.sap.com/docs/successfactors-recruiting/setting-up-and-maintaining-sap-successfactors-recruiting/working-with-resume-parsing",
            "https://help.sap.com/docs/successfactors-recruiting/setting-up-and-maintaining-sap-successfactors-recruiting/candidate-profile-in-sap-successfactors",
        ],
    },
    "taleo": {
        "display": "Oracle Taleo",
        "domains": ["taleo.net"],
        "format_rules": COMMON_FORMAT_RULES + [
            "keep personal information, education, employer, job function, responsibilities, and dates explicit",
            "use compact conventional chronology because Taleo resume parsing extracts standard candidate fields",
        ],
        "evidence": ["https://docs.oracle.com/en/cloud/saas/taleo-enterprise/20b/otrec/using-recruiting.pdf"],
    },
    "icims": {
        "display": "iCIMS",
        "domains": ["icims.com"],
        "format_rules": COMMON_FORMAT_RULES + [
            "use supported acronyms and expanded skill names naturally when both are accurate",
            "avoid keyword repetition that is not backed by experience evidence",
        ],
        "evidence": ["https://www.icims.com/glossary/applicant-tracking-system-ats/"],
    },
    "lever": {
        "display": "Lever",
        "domains": ["lever.co"],
        "format_rules": COMMON_FORMAT_RULES,
        "evidence": ["https://help.lever.co/"],
    },
    "ashby": {
        "display": "Ashby",
        "domains": ["ashbyhq.com"],
        "format_rules": COMMON_FORMAT_RULES,
        "evidence": ["https://help.ashbyhq.com/"],
    },
    "eightfold": {
        "display": "Eightfold",
        "domains": ["eightfold.ai"],
        "format_rules": COMMON_FORMAT_RULES + ["prefer evidence-rich skills context over isolated keyword lists"],
        "evidence": ["https://eightfold.ai/"],
    },
    "phenom": {
        "display": "Phenom",
        "domains": ["phenompeople.com", "phenom.com"],
        "format_rules": COMMON_FORMAT_RULES,
        "evidence": ["https://www.phenom.com/"],
    },
    "paradox": {
        "display": "Paradox",
        "domains": ["paradox.ai", "paradoxolivia.com"],
        "format_rules": COMMON_FORMAT_RULES,
        "evidence": ["https://paradox.ai/"],
    },
    "unknown": {
        "display": "Unknown / Common-Denominator ATS",
        "domains": [],
        "format_rules": COMMON_FORMAT_RULES,
        "evidence": [],
    },
}

OFFICIAL_EVIDENCE_DOMAINS: dict[str, set[str]] = {
    "workday": {"workday.com", "doc.workday.com"},
    "greenhouse": {"greenhouse.com", "support.greenhouse.io"},
    "smartrecruiters": {"smartrecruiters.com"},
    "successfactors": {"sap.com", "help.sap.com"},
    "taleo": {"oracle.com", "docs.oracle.com"},
    "icims": {"icims.com"},
    "lever": {"lever.co", "help.lever.co"},
    "ashby": {"ashbyhq.com", "help.ashbyhq.com"},
    "eightfold": {"eightfold.ai"},
    "phenom": {"phenom.com", "phenompeople.com"},
    "paradox": {"paradox.ai", "paradoxolivia.com"},
}

def _is_official_vendor_evidence(provider: str, url: str) -> bool:
    domain = _normalized_domain(url)
    return any(domain == allowed or domain.endswith("." + allowed) for allowed in OFFICIAL_EVIDENCE_DOMAINS.get(provider, set()))

# Only deterministic aliases are allowed. Do not use semantic similarity to invent experience.
ALIASES = {
    "iam": {"iam", "identity and access management", "identity access management"},
    "mfa": {"mfa", "multi factor authentication", "multi-factor authentication"},
    "ci/cd": {"ci/cd", "cicd", "continuous integration continuous delivery", "continuous integration and delivery"},
    "genai": {"genai", "generative ai", "generative artificial intelligence"},
    "llm": {"llm", "large language model", "large language models"},
    "rbac": {"rbac", "role based access control", "role-based access control"},
    "abac": {"abac", "attribute based access control", "attribute-based access control"},
    "bomgar": {"bomgar", "beyondtrust remote support"},
}

LANE_TERMS = {
    "AI_PLATFORM_AGENTIC": {
        "agentic ai", "ai platform", "llm", "genai", "rag", "fastapi", "python", "model routing",
        "ai engineer", "ai architect", "automation", "cloud ai", "multi cloud", "multi-cloud", "devops",
    },
    "AI_GOVERNANCE_CYBERSECURITY": {
        "ai governance", "responsible ai", "ai security", "cybersecurity", "application security", "iam",
        "provenance", "audit", "policy", "guardrail", "trust", "zero trust", "risk", "identity", "devsecops",
    },
    "ENTERPRISE_SUPPORT": {
        "technical support", "service desk", "help desk", "it support", "servicenow", "remedy", "vpn", "mfa",
        "endpoint", "desktop support", "incident", "sla", "beyondtrust", "bomgar",
    },
}


class ATSDetectionRequest(BaseModel):
    application_url: str = Field(min_length=8, max_length=2048)
    page_text_hint: str = Field(default="", max_length=10000)

    @field_validator("application_url")
    @classmethod
    def validate_application_url(cls, value: str) -> str:
        _normalized_domain(value)
        return value


class VendorChange(BaseModel):
    event_id: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    provider: Provider
    title: str = Field(min_length=3, max_length=240)
    detail: str = Field(min_length=3, max_length=4000)
    evidence_url: str = Field(min_length=8, max_length=2048)
    published_at: datetime
    observed_at: datetime = Field(default_factory=_utcnow)
    evidence_state: EvidenceState = "VERIFIED"
    change_type: Literal[
        "format_compatibility", "skills_matching", "candidate_profile", "application_data",
        "screening_workflow", "consent_privacy", "other"
    ] = "other"
    resume_impact: Literal["NONE", "REVIEW", "ADAPT"] = "REVIEW"
    tailoring_directive: str | None = Field(default=None, max_length=600)
    expires_at: datetime | None = None

    @field_validator("evidence_url")
    @classmethod
    def validate_https(cls, value: str) -> str:
        _normalized_domain(value)
        return value

    @field_validator("tailoring_directive")
    @classmethod
    def validate_directive(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if any(ord(ch) < 32 and ch not in "\t\n" for ch in value):
            raise ValueError("tailoring directive contains control characters")
        return value.strip() or None


class EmployerRule(BaseModel):
    rule_id: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    employer: str = Field(min_length=2, max_length=200)
    business_unit: str | None = Field(default=None, max_length=200)
    scope: Literal["company", "business_unit", "job"]
    job_key: str | None = Field(default=None, max_length=240)
    rule_type: Literal[
        "required_skill", "preferred_skill", "screening_question", "remote_rule", "compensation",
        "clearance", "citizenship", "education", "experience", "title_taxonomy", "ats_platform", "other"
    ]
    value: str = Field(min_length=1, max_length=2000)
    evidence_url: str = Field(min_length=8, max_length=2048)
    observed_at: datetime
    evidence_state: EvidenceState = "VERIFIED"
    expires_at: datetime | None = None

    @field_validator("evidence_url")
    @classmethod
    def validate_https(cls, value: str) -> str:
        _normalized_domain(value)
        return value


class TailoringRequest(BaseModel):
    employer: str = Field(min_length=2, max_length=200)
    business_unit: str | None = Field(default=None, max_length=200)
    job_key: str | None = Field(default=None, max_length=240)
    job_title: str = Field(min_length=2, max_length=240)
    job_description: str = Field(default="", max_length=30000)
    application_url: str = Field(min_length=8, max_length=2048)
    required_skills: list[str] = Field(default_factory=list, max_length=100)
    preferred_skills: list[str] = Field(default_factory=list, max_length=100)
    candidate_skills: list[str] = Field(default_factory=list, max_length=500)
    candidate_facts: list[str] = Field(default_factory=list, max_length=1000)

    @field_validator("application_url")
    @classmethod
    def validate_application_url(cls, value: str) -> str:
        _normalized_domain(value)
        return value

    @field_validator("required_skills", "preferred_skills", "candidate_skills")
    @classmethod
    def validate_skill_items(cls, values: list[str]) -> list[str]:
        if any(not isinstance(v, str) or not v.strip() or len(v) > 300 for v in values):
            raise ValueError("skill entries must be non-empty and <=300 characters")
        if sum(len(v) for v in values) > 60000:
            raise ValueError("skill evidence payload too large")
        return values

    @field_validator("candidate_facts")
    @classmethod
    def validate_candidate_facts(cls, values: list[str]) -> list[str]:
        if any(not isinstance(v, str) or not v.strip() or len(v) > 1000 for v in values):
            raise ValueError("candidate facts must be non-empty and <=1000 characters")
        if sum(len(v) for v in values) > 150000:
            raise ValueError("candidate fact payload too large")
        return values


@dataclass(frozen=True)
class Detection:
    provider: str
    confidence: str
    matched_domain: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"provider": self.provider, "confidence": self.confidence, "matched_domain": self.matched_domain}


class ATSStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._initialize()

    @classmethod
    def from_env(cls) -> "ATSStore":
        return cls(_data_dir() / "sara_omega.db")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def _initialize(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS ats_vendor_events(
                    event_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ats_employer_rules(
                    rule_id TEXT PRIMARY KEY,
                    employer_key TEXT NOT NULL,
                    business_unit_key TEXT,
                    scope TEXT NOT NULL,
                    job_key TEXT,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ats_idempotency(
                    idempotency_key TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ats_audit(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    evidence_state TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _hash(payload: dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        return hashlib.sha256(body).hexdigest()

    def _reserve(self, key: str, operation: str, payload: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
        payload_hash = self._hash(payload)
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT * FROM ats_idempotency WHERE idempotency_key=?", (key,)).fetchone()
            if row:
                if row["operation"] != operation or row["payload_hash"] != payload_hash:
                    raise ValueError("idempotency_key_reused_with_different_payload")
                prior = json.loads(row["result_json"])
                if prior.get("status") == "RESERVED":
                    prior = {"status": "SUBMISSION_UNVERIFIED", "reason": "prior_mutation_outcome_unknown", "automatic_retry": False}
                    conn.execute(
                        "UPDATE ats_idempotency SET result_json=? WHERE idempotency_key=?",
                        (json.dumps(prior, sort_keys=True), key),
                    )
                return False, prior
            conn.execute(
                "INSERT INTO ats_idempotency(idempotency_key,operation,payload_hash,result_json,created_at) VALUES(?,?,?,?,?)",
                (key, operation, payload_hash, json.dumps({"status": "RESERVED"}), _iso()),
            )
        return True, None

    def _complete(self, key: str, result: dict[str, Any]) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE ats_idempotency SET result_json=? WHERE idempotency_key=?", (json.dumps(result, sort_keys=True), key))

    def save_vendor_change(self, change: VendorChange, idempotency_key: str) -> dict[str, Any]:
        payload = change.model_dump(mode="json")
        fresh, prior = self._reserve(idempotency_key, "vendor_change", payload)
        if not fresh:
            return prior or {"status": "UNKNOWN"}
        if change.evidence_state == "VERIFIED" and not _is_official_vendor_evidence(change.provider, change.evidence_url):
            result = {"status": "REJECTED", "reason": "verified_vendor_evidence_not_official", "automatic_retry": False}
            self._complete(idempotency_key, result)
            raise ValueError("verified_vendor_evidence_not_official")
        payload_hash = self._hash(payload)
        try:
            with closing(self._connect()) as conn, conn:
                existing = conn.execute("SELECT payload_hash FROM ats_vendor_events WHERE event_id=?", (change.event_id,)).fetchone()
                if existing and existing["payload_hash"] != payload_hash:
                    raise ValueError("event_id_conflict")
                conn.execute(
                    "INSERT OR IGNORE INTO ats_vendor_events(event_id,provider,payload_json,payload_hash,created_at) VALUES(?,?,?,?,?)",
                    (change.event_id, change.provider, json.dumps(payload, sort_keys=True), payload_hash, _iso()),
                )
                conn.execute(
                    "INSERT INTO ats_audit(event_type,subject,evidence_state,payload_hash,created_at) VALUES(?,?,?,?,?)",
                    ("vendor_change", change.provider, change.evidence_state, payload_hash, _iso()),
                )
            result = {"status": "ACCEPTED", "event_id": change.event_id, "payload_hash": payload_hash}
            self._complete(idempotency_key, result)
            return result
        except ValueError as exc:
            self._complete(idempotency_key, {"status": "REJECTED", "reason": str(exc), "automatic_retry": False})
            raise
        except Exception:
            self._complete(idempotency_key, {"status": "SUBMISSION_UNVERIFIED", "reason": "mutation_outcome_unknown", "automatic_retry": False})
            raise

    def save_employer_rule(self, rule: EmployerRule, idempotency_key: str) -> dict[str, Any]:
        payload = rule.model_dump(mode="json")
        fresh, prior = self._reserve(idempotency_key, "employer_rule", payload)
        if not fresh:
            return prior or {"status": "UNKNOWN"}
        payload_hash = self._hash(payload)
        employer_key = _normalize(rule.employer)
        business_key = _normalize(rule.business_unit or "") or None
        try:
            with closing(self._connect()) as conn, conn:
                existing = conn.execute("SELECT payload_hash FROM ats_employer_rules WHERE rule_id=?", (rule.rule_id,)).fetchone()
                if existing and existing["payload_hash"] != payload_hash:
                    raise ValueError("rule_id_conflict")
                conn.execute(
                    "INSERT OR IGNORE INTO ats_employer_rules(rule_id,employer_key,business_unit_key,scope,job_key,payload_json,payload_hash,created_at) VALUES(?,?,?,?,?,?,?,?)",
                    (rule.rule_id, employer_key, business_key, rule.scope, rule.job_key, json.dumps(payload, sort_keys=True), payload_hash, _iso()),
                )
                conn.execute(
                    "INSERT INTO ats_audit(event_type,subject,evidence_state,payload_hash,created_at) VALUES(?,?,?,?,?)",
                    ("employer_rule", f"{employer_key}:{business_key or '*'}", rule.evidence_state, payload_hash, _iso()),
                )
            result = {"status": "ACCEPTED", "rule_id": rule.rule_id, "payload_hash": payload_hash}
            self._complete(idempotency_key, result)
            return result
        except ValueError as exc:
            self._complete(idempotency_key, {"status": "REJECTED", "reason": str(exc), "automatic_retry": False})
            raise
        except Exception:
            self._complete(idempotency_key, {"status": "SUBMISSION_UNVERIFIED", "reason": "mutation_outcome_unknown", "automatic_retry": False})
            raise

    def applicable_vendor_changes(self, provider: str, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or _utcnow()
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT payload_json FROM ats_vendor_events WHERE provider=? ORDER BY created_at DESC",
                (provider,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            if payload.get("evidence_state") != "VERIFIED":
                continue
            observed_at = datetime.fromisoformat(payload.get("observed_at") or payload["published_at"])
            expires_at = datetime.fromisoformat(payload["expires_at"]) if payload.get("expires_at") else observed_at + timedelta(days=30)
            if now > expires_at:
                continue
            if payload.get("resume_impact") not in {"REVIEW", "ADAPT"}:
                continue
            out.append(payload)
        return out[:50]

    def applicable_rules(self, employer: str, business_unit: str | None, job_key: str | None, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or _utcnow()
        employer_key = _normalize(employer)
        bu_key = _normalize(business_unit or "") or None
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM ats_employer_rules WHERE employer_key=?", (employer_key,)).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            observed_at = datetime.fromisoformat(payload["observed_at"])
            expires_at = datetime.fromisoformat(payload["expires_at"]) if payload.get("expires_at") else observed_at + timedelta(days=14)
            if now > expires_at:
                continue
            scope = payload["scope"]
            if scope == "company":
                out.append(payload)
            elif scope == "business_unit" and bu_key and row["business_unit_key"] == bu_key:
                out.append(payload)
            elif scope == "job" and job_key and row["job_key"] == job_key:
                if row["business_unit_key"] in {None, bu_key}:
                    out.append(payload)
        return out

    def latest_vendor_observation(self, provider: str) -> datetime | None:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT payload_json FROM ats_vendor_events WHERE provider=? ORDER BY created_at DESC",
                (provider,),
            ).fetchall()
        latest: datetime | None = None
        for row in rows:
            payload = json.loads(row["payload_json"])
            if payload.get("evidence_state") != "VERIFIED":
                continue
            observed = datetime.fromisoformat(payload.get("observed_at") or payload["published_at"])
            if latest is None or observed > latest:
                latest = observed
        return latest

    def counts(self) -> dict[str, int]:
        with closing(self._connect()) as conn:
            vendor = conn.execute("SELECT COUNT(*) FROM ats_vendor_events").fetchone()[0]
            rules = conn.execute("SELECT COUNT(*) FROM ats_employer_rules").fetchone()[0]
        return {"vendor_events": int(vendor), "employer_rules": int(rules)}


class ATSIntelligenceService:
    def __init__(self, store: ATSStore | None = None):
        self.store = store or ATSStore.from_env()

    @staticmethod
    def detect(application_url: str, page_text_hint: str = "") -> Detection:
        domain = _normalized_domain(application_url)
        for provider, profile in PROFILES.items():
            if provider == "unknown":
                continue
            for known in profile["domains"]:
                if domain == known or domain.endswith("." + known):
                    return Detection(provider, "VERIFIED_DOMAIN", known)
        hint = _normalize(page_text_hint)
        hint_markers = {
            "workday": ["workday"],
            "greenhouse": ["greenhouse"],
            "smartrecruiters": ["smartrecruiters", "winston match"],
            "successfactors": ["successfactors", "success factors"],
            "taleo": ["taleo"],
            "icims": ["icims"],
            "lever": ["lever jobs"],
            "ashby": ["ashby"],
            "eightfold": ["eightfold"],
            "phenom": ["phenom"],
            "paradox": ["paradox", "olivia recruiting"],
        }
        for provider, markers in hint_markers.items():
            if any(marker in hint for marker in markers):
                return Detection(provider, "SUPPORTED_HINT", None)
        return Detection("unknown", "UNVERIFIED", None)

    @staticmethod
    def _auth_token() -> str:
        token = os.getenv("SARA_ATS_INTELLIGENCE_AUTH_TOKEN", "").strip()
        forbidden_names = (
            "OWNER_TOKEN", "GPT_ACTION_TOKEN", "TEST_TOKEN", "SARA_RAILWAY_CONTROL_AUTH_TOKEN",
            "SARA_SOURCE_CONTROL_AUTH_TOKEN", "SARA_DEVICE_CONTROL_AUTH_TOKEN",
        )
        forbidden = {os.getenv(name, "").strip() for name in forbidden_names}
        forbidden.discard("")
        if not token or token in forbidden:
            return ""
        return token

    def authorize_mutation(self, authorization: str | None) -> None:
        token = self._auth_token()
        if not token:
            raise HTTPException(503, "ATS intelligence mutation authority is not separately configured")
        supplied = (authorization or "").removeprefix("Bearer ").strip()
        if not supplied or not hmac.compare_digest(supplied, token):
            raise HTTPException(403, "ATS intelligence mutation authority rejected")

    def profile_freshness(self, provider: str, now: datetime | None = None) -> dict[str, Any]:
        now = now or _utcnow()
        if provider == "unknown":
            return {"state": "COMMON_DENOMINATOR", "requires_revalidation": False, "last_verified_at": None}
        latest = self.store.latest_vendor_observation(provider)
        last_verified = max([x for x in (BASELINE_CHECKED_AT, latest) if x is not None])
        try:
            max_age_hours = max(6, min(int(os.getenv("SARA_ATS_PROFILE_MAX_AGE_HOURS", "48")), 720))
        except ValueError:
            max_age_hours = 48
        age_hours = max(0.0, (now - last_verified).total_seconds() / 3600)
        stale = age_hours > max_age_hours
        return {
            "state": "STALE_REVALIDATION_REQUIRED" if stale else "FRESH",
            "requires_revalidation": stale,
            "last_verified_at": _iso(last_verified),
            "age_hours": round(age_hours, 2),
            "max_age_hours": max_age_hours,
        }

    @staticmethod
    def _skill_supported(skill: str, candidate_blob: str) -> bool:
        needle = _normalize(skill)
        if not needle:
            return False
        if needle in candidate_blob:
            return True
        for canonical, variants in ALIASES.items():
            normalized_variants = {_normalize(v) for v in variants}
            if needle == canonical or needle in normalized_variants:
                return any(v in candidate_blob for v in normalized_variants)
        return False

    @staticmethod
    def select_lane(job_title: str, job_description: str) -> ResumeLane:
        blob = _normalize(job_title + " " + job_description)
        scores = {lane: sum(1 for term in terms if _normalize(term) in blob) for lane, terms in LANE_TERMS.items()}
        # Ties prefer the narrower truthful governance lane, then platform, then support.
        order = ["AI_GOVERNANCE_CYBERSECURITY", "AI_PLATFORM_AGENTIC", "ENTERPRISE_SUPPORT"]
        return max(order, key=lambda lane: (scores[lane], -order.index(lane)))  # type: ignore[return-value]

    def tailoring_plan(self, request: TailoringRequest) -> dict[str, Any]:
        detection = self.detect(request.application_url)
        freshness = self.profile_freshness(detection.provider)
        profile = PROFILES["unknown"] if freshness["requires_revalidation"] else PROFILES[detection.provider]
        candidate_blob = _normalize(" ".join(request.candidate_skills + request.candidate_facts))
        supported_required = [s for s in request.required_skills if self._skill_supported(s, candidate_blob)]
        hard_gaps = [s for s in request.required_skills if s not in supported_required]
        supported_preferred = [s for s in request.preferred_skills if self._skill_supported(s, candidate_blob)]
        rules = self.store.applicable_rules(request.employer, request.business_unit, request.job_key)
        vendor_changes = self.store.applicable_vendor_changes(detection.provider) if detection.provider != "unknown" else []
        adaptive_directives = [
            item["tailoring_directive"] for item in vendor_changes
            if item.get("resume_impact") == "ADAPT" and item.get("tailoring_directive")
        ]
        lane = self.select_lane(request.job_title, request.job_description)
        return {
            "status": "PASS" if not hard_gaps and not freshness["requires_revalidation"] else "PARTIAL",
            "epistemic_state": "VERIFIED" if detection.confidence == "VERIFIED_DOMAIN" else "SUPPORTED" if detection.confidence == "SUPPORTED_HINT" else "UNVERIFIED",
            "provider": detection.as_dict(),
            "profile_version": ATS_PROFILE_VERSION,
            "profile_freshness": freshness,
            "resume_lane": lane,
            "format_rules": list(profile["format_rules"]),
            "supported_required_skills": supported_required,
            "supported_preferred_skills": supported_preferred,
            "hard_gaps": hard_gaps,
            "current_vendor_changes": vendor_changes,
            "adaptive_directives": adaptive_directives,
            "applicable_employer_rules": rules,
            "rewrite_policy": "Reorder and rephrase only facts already present in candidate evidence; never create qualifications, credentials, dates, metrics, tools, duties, or outcomes.",
            "keyword_policy": "Use only supported job vocabulary in natural context; hidden keywords and unsupported keyword stuffing are prohibited.",
        }

    @staticmethod
    def git_commit() -> str:
        for name in ("RAILWAY_GIT_COMMIT_SHA", "RAILWAY_GIT_COMMIT", "GIT_COMMIT_SHA", "SOURCE_COMMIT_SHA"):
            value = os.getenv(name, "").strip()
            if re.fullmatch(r"[0-9a-fA-F]{7,64}", value):
                return value.lower()
        return "UNVERIFIED"

    def health(self) -> dict[str, Any]:
        token_ready = bool(self._auth_token())
        counts = self.store.counts()
        return {
            "status": "ok",
            "module": MODULE_NAME,
            "present": True,
            "version": ATS_PROFILE_VERSION,
            "profile_count": len(PROFILES),
            "providers": sorted(PROFILES),
            "store_ready": self.store.db_path.exists(),
            "mutation_authority_separate": token_ready,
            "execution_authority": False,
            "truth_preserving_tailoring": True,
            "business_unit_scope_isolation": True,
            "stale_rule_suppression": True,
            "dynamic_vendor_overlays": True,
            "profile_freshness_fail_closed": True,
            "uncertain_mutation_no_retry": True,
            "counts": counts,
            "git_commit": self.git_commit(),
        }


_service_instance: ATSIntelligenceService | None = None


def get_service() -> ATSIntelligenceService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ATSIntelligenceService()
    return _service_instance


router = APIRouter(prefix="/ats-intelligence", tags=["ATS Intelligence"])


@router.get("/health")
def ats_health():
    return get_service().health()


@router.get("/attestation")
def ats_attestation():
    h = get_service().health()
    return {
        "module": h["module"],
        "version": h["version"],
        "git_commit": h["git_commit"],
        "store_ready": h["store_ready"],
        "truth_preserving_tailoring": h["truth_preserving_tailoring"],
        "business_unit_scope_isolation": h["business_unit_scope_isolation"],
        "stale_rule_suppression": h["stale_rule_suppression"],
        "dynamic_vendor_overlays": h["dynamic_vendor_overlays"],
        "profile_freshness_fail_closed": h["profile_freshness_fail_closed"],
        "uncertain_mutation_no_retry": h["uncertain_mutation_no_retry"],
        "execution_authority": False,
    }


@router.post("/detect")
def ats_detect(payload: ATSDetectionRequest):
    return get_service().detect(payload.application_url, payload.page_text_hint).as_dict()


@router.get("/profiles")
def ats_profiles():
    return {"version": ATS_PROFILE_VERSION, "profiles": PROFILES}


@router.post("/tailor-plan")
def ats_tailor_plan(payload: TailoringRequest):
    return get_service().tailoring_plan(payload)


@router.post("/vendor-change")
def ats_vendor_change(
    payload: VendorChange,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    current = get_service()
    current.authorize_mutation(authorization)
    if not idempotency_key or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
        raise HTTPException(400, "valid Idempotency-Key required")
    try:
        return current.store.save_vendor_change(payload, idempotency_key)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/employer-rule")
def ats_employer_rule(
    payload: EmployerRule,
    authorization: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    current = get_service()
    current.authorize_mutation(authorization)
    if not idempotency_key or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
        raise HTTPException(400, "valid Idempotency-Key required")
    try:
        return current.store.save_employer_rule(payload, idempotency_key)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
