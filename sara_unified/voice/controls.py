from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum


class SpeechRate(StrEnum):
    SLOWER = "slower"
    NORMAL = "normal"
    FASTER = "faster"


@dataclass(frozen=True)
class SynthesisControls:
    speech_rate: SpeechRate
    length_scale: float
    noise_scale: float = 0.55
    noise_w_scale: float = 0.70
    volume: float = 0.95

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, default=str).encode("utf-8")).hexdigest()


_CONTROLS = {
    SpeechRate.SLOWER: SynthesisControls(SpeechRate.SLOWER, length_scale=1.16),
    SpeechRate.NORMAL: SynthesisControls(SpeechRate.NORMAL, length_scale=1.08),
    SpeechRate.FASTER: SynthesisControls(SpeechRate.FASTER, length_scale=1.00),
}


def speech_controls_for(rate: SpeechRate | str) -> SynthesisControls:
    try:
        normalized = rate if isinstance(rate, SpeechRate) else SpeechRate(str(rate))
    except ValueError as exc:
        raise ValueError("unsupported speech rate") from exc
    return _CONTROLS[normalized]
