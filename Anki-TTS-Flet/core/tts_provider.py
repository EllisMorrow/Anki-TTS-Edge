from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.tts_types import SynthesisRequest, SynthesisResult


class TTSProvider(ABC):
    provider_id: str

    @abstractmethod
    def is_ready(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def supports_language(self, language_hint: str, text: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        raise NotImplementedError

    def list_voices(self) -> list[dict[str, Any]]:
        return []

