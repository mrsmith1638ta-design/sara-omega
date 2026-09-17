from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceSegment:
    segment_id: str
    index: int
    text: str
    text_sha256: str
    character_count: int


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def split_sentences(
    text: str,
    *,
    max_segments: int = 64,
    max_segment_characters: int = 600,
) -> list[VoiceSegment]:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        raise ValueError("voice text must not be empty")
    if max_segments <= 0:
        raise ValueError("max_segments must be positive")
    if max_segment_characters <= 0:
        raise ValueError("max_segment_characters must be positive")

    raw_segments = [part.strip() for part in _SENTENCE_BOUNDARY.split(cleaned) if part.strip()]
    expanded: list[str] = []
    for raw in raw_segments:
        if len(raw) <= max_segment_characters:
            expanded.append(raw)
            continue
        words = raw.split()
        current: list[str] = []
        current_length = 0
        for word in words:
            next_length = current_length + len(word) + (1 if current else 0)
            if current and next_length > max_segment_characters:
                expanded.append(" ".join(current))
                current = [word]
                current_length = len(word)
            else:
                current.append(word)
                current_length = next_length
        if current:
            expanded.append(" ".join(current))

    if len(expanded) > max_segments:
        raise ValueError("too many voice segments")

    return [
        VoiceSegment(
            segment_id=f"seg-{index:04d}",
            index=index,
            text=segment,
            text_sha256=hashlib.sha256(segment.encode("utf-8")).hexdigest(),
            character_count=len(segment),
        )
        for index, segment in enumerate(expanded, start=1)
    ]
