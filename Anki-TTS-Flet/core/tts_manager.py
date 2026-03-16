from __future__ import annotations

from core.tts_edge_provider import EdgeTTSProvider
from core.tts_local_kokoro_provider import LocalKokoroProvider
from core.tts_provider import TTSProvider
from core.tts_types import SynthesisRequest, SynthesisResult


class TTSManager:
    def __init__(self, settings_manager):
        self._settings = settings_manager
        self._providers: dict[str, TTSProvider] = {}
        self.register(EdgeTTSProvider())
        self.register(LocalKokoroProvider(settings_manager))

    def register(self, provider: TTSProvider) -> None:
        self._providers[provider.provider_id] = provider

    def get_engine_id(self) -> str:
        return self._settings.get("tts_engine", "edge_online") or "edge_online"

    def get_provider(self, engine_id: str) -> TTSProvider:
        return self._providers.get(engine_id) or self._providers["edge_online"]

    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        engine_id = request.engine or self.get_engine_id()
        provider = self.get_provider(engine_id)

        result = await provider.synthesize(request)
        if result.ok:
            return result

        # Automatic fallback: if user selected local engine but it's not ready, fall back to Edge.
        if engine_id != "edge_online" and self._settings.get("local_engine_auto_fallback", True):
            edge_provider = self.get_provider("edge_online")
            fallback_req = SynthesisRequest(**{**request.__dict__, "engine": "edge_online"})
            fallback_res = await edge_provider.synthesize(fallback_req)
            if fallback_res.ok:
                fallback_res.metadata["fallback_from"] = engine_id
                return fallback_res

        return result
