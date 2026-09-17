from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PronunciationRule:
    match: str
    replacement: str


@dataclass(frozen=True)
class PronunciationResult:
    text: str
    dictionary_id: str
    dictionary_version: str
    dictionary_sha256: str
    applied_rules: list[str]


@dataclass(frozen=True)
class PronunciationDictionary:
    dictionary_id: str
    version: str
    rules: tuple[PronunciationRule, ...] = ()
    max_output_characters: int = 5000

    @classmethod
    def default(cls) -> "PronunciationDictionary":
        return cls(
            dictionary_id="sara-default",
            version="2026.09.17",
            rules=(
                PronunciationRule("SARA OMEGA", "Sarah Omega"),
                PronunciationRule("SARA", "Sarah"),
            ),
        )

    @property
    def sha256(self) -> str:
        payload = {
            "dictionary_id": self.dictionary_id,
            "version": self.version,
            "rules": [asdict(rule) for rule in self.rules],
            "max_output_characters": self.max_output_characters,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def apply(self, text: str) -> PronunciationResult:
        transformed = text
        applied: list[str] = []
        for rule in self.rules:
            if rule.match in transformed:
                transformed = transformed.replace(rule.match, rule.replacement)
                applied.append(rule.match)
        if len(transformed) > self.max_output_characters:
            raise ValueError("pronunciation output exceeds maximum length")
        return PronunciationResult(
            text=transformed,
            dictionary_id=self.dictionary_id,
            dictionary_version=self.version,
            dictionary_sha256=self.sha256,
            applied_rules=applied,
        )
