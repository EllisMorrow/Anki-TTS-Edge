from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TimestampsPayload:
    """
    Unified timestamps structure.

    - Edge TTS fills words/sentences.
    - Local engines (V1) return empty lists but keep the same shape for future upgrades.
    """

    text: str = ""
    words: list[dict[str, Any]] = field(default_factory=list)
    sentences: list[dict[str, Any]] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text or "",
            "words": self.words or [],
            "sentences": self.sentences or [],
            "source": self.source or "",
        }


@dataclass
class SynthesisRequest:
    text: str
    voice: str
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"
    engine: str = "edge_online"
    output_path: str = ""
    language_hint: str = ""
    # Local engines may use numeric speaker IDs (e.g. Kokoro sid).
    # Keep voice as the Edge voice name so automatic fallback to Edge stays functional.
    speaker_id: int | None = None


@dataclass
class SynthesisResult:
    ok: bool
    engine: str
    audio_path: str = ""
    error: str = ""
    timestamps: TimestampsPayload | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
