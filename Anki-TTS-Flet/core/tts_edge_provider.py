from __future__ import annotations

from core.audio_gen import generate_audio_task
from core.tts_provider import TTSProvider
from core.tts_types import SynthesisRequest, SynthesisResult, TimestampsPayload
from utils.text import sanitize_text


class EdgeTTSProvider(TTSProvider):
    provider_id = "edge_online"

    def is_ready(self) -> bool:
        return True

    def supports_language(self, language_hint: str, text: str) -> bool:
        # Edge voice list is global and dynamic. We don't attempt strict filtering here.
        return True

    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        text = sanitize_text(request.text or "")
        if not text:
            return SynthesisResult(ok=False, engine=self.provider_id, error="empty_text")

        path, error, timestamps = await generate_audio_task(
            text,
            request.voice,
            request.rate,
            request.volume,
            request.pitch,
        )

        if not path:
            return SynthesisResult(ok=False, engine=self.provider_id, error=error or "edge_tts_failed")

        ts_payload = None
        if isinstance(timestamps, dict):
            ts_payload = TimestampsPayload(
                text=timestamps.get("text") or text,
                words=timestamps.get("words") or [],
                sentences=timestamps.get("sentences") or [],
                source="edge_tts",
            )

        return SynthesisResult(
            ok=True,
            engine=self.provider_id,
            audio_path=path,
            timestamps=ts_payload,
        )

