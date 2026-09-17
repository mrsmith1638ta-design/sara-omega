from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecoveryRequest(BaseModel):
    context: dict[str,Any] = Field(default_factory=dict)
    approved: bool = False


class CounterfactualRequest(BaseModel):
    baseline: dict[str,Any]
    changes: dict[str,Any]


class JuryOpinionInput(BaseModel):
    model_id: str
    conclusion: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)


class JuryRequest(BaseModel):
    opinions: list[JuryOpinionInput] = Field(min_length=1)


class IncidentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    severity: str = Field(pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    affected: list[str] = Field(default_factory=list, max_length=100)


class TwinObservationRequest(BaseModel):
    entity_id: str = Field(min_length=1, max_length=200)
    state: dict[str,Any]
    verified: bool
    source: str = Field(min_length=1, max_length=200)


class VoiceSynthesisRequest(BaseModel):
    text: str = Field(min_length=1)


class VoiceJobRequest(BaseModel):
    text: str = Field(min_length=1)
    speech_rate: str = Field(default="normal")
    preserve_transcript: bool = False
    return_audio: str = Field(default="none")


class VoiceAccessibilityJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4000)
    speech_rate: Literal["slower", "normal", "faster"] | None = None
    preserve_transcript: bool | None = None


class VoiceAccessibilityPreferencesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speech_rate: Literal["slower", "normal", "faster"]
    preserve_transcript: bool
    transcript_retention_seconds: Literal[0, 900, 3600, 86400]

    @model_validator(mode="after")
    def validate_retention(self):
        if self.preserve_transcript != (self.transcript_retention_seconds > 0):
            raise ValueError("transcript retention does not match preservation choice")
        return self


class VoiceAccessibilityEntitlementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_user_id: str = Field(pattern=r"^SARA-U-[A-F0-9]{12}$")
    expires_at: datetime | None = None
