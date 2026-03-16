from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from config.constants import AUDIO_DIR
from core.local_engine_manager import LocalEngineManager
from core.tts_provider import TTSProvider
from core.tts_types import SynthesisRequest, SynthesisResult, TimestampsPayload
from utils.text import sanitize_text


def _guess_language(text: str) -> str:
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return "zh"
    return "en"


class LocalKokoroProvider(TTSProvider):
    provider_id = "local_kokoro"

    def __init__(self, settings_manager):
        self._settings = settings_manager
        self._engine = LocalEngineManager(settings_manager)

    def is_ready(self) -> bool:
        return bool(self._engine.validate_installation().get("ok", False))

    def supports_language(self, language_hint: str, text: str) -> bool:
        hint = (language_hint or "").strip().lower()
        if hint:
            return hint.startswith("zh") or hint.startswith("en")
        guessed = _guess_language(text or "")
        return guessed in {"zh", "en"}

    def _build_output_path(self, request: SynthesisRequest, sid: int) -> str:
        cache_payload = json.dumps(
            {
                "engine": self.provider_id,
                "text": request.text or "",
                "sid": sid,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        cache_key = hashlib.sha1(cache_payload.encode("utf-8")).hexdigest()
        fname = f"Anki-TTS-Edge_kokoro_sid{sid}_{cache_key[:16]}.wav"
        return os.path.join(AUDIO_DIR, fname)

    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        text = sanitize_text(request.text or "")
        if not text:
            return SynthesisResult(ok=False, engine=self.provider_id, error="empty_text")

        auto_fallback = bool(self._settings.get("local_engine_auto_fallback", True))
        if not self.supports_language(request.language_hint, text) and auto_fallback:
            return SynthesisResult(ok=False, engine=self.provider_id, error="unsupported_language")

        validation = self._engine.validate_installation()
        if not validation.get("ok"):
            return SynthesisResult(ok=False, engine=self.provider_id, error=validation.get("error") or "engine_not_ready")

        runtime_exe = Path(validation["runtime_exe"])
        model_dir = Path(validation["model_dir"])
        model_onnx = Path(validation.get("model_onnx") or (model_dir / "model.onnx"))

        # V1: use a single speaker id by default. Future: map local voice selection to sid.
        sid = 0

        out_path = request.output_path or self._build_output_path(request, sid)
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        if out_file.exists() and out_file.stat().st_size > 1024:
            return SynthesisResult(
                ok=True,
                engine=self.provider_id,
                audio_path=str(out_file),
                timestamps=TimestampsPayload(text=text, words=[], sentences=[], source="local_kokoro:none"),
                metadata={"cache_hit": True},
            )

        cmd = [
            str(runtime_exe),
            f"--kokoro-model={model_onnx}",
            f"--kokoro-voices={model_dir / 'voices.bin'}",
            f"--kokoro-tokens={model_dir / 'tokens.txt'}",
        ]

        espeak_dir = model_dir / "espeak-ng-data"
        if espeak_dir.exists():
            cmd.append(f"--kokoro-data-dir={espeak_dir}")
        lex_en = model_dir / "lexicon-us-en.txt"
        lex_zh = model_dir / "lexicon-zh.txt"
        if lex_en.exists() and lex_zh.exists():
            cmd.append(f"--kokoro-lexicon={lex_en},{lex_zh}")

        cmd.append(f"--output-filename={out_file}")
        cmd.append(f"--sid={sid}")
        cmd.append(text)

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                cwd=str(self._engine.base_dir),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as ex:
            return SynthesisResult(ok=False, engine=self.provider_id, error=str(ex))

        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()[:2000]
            return SynthesisResult(ok=False, engine=self.provider_id, error=f"kokoro_failed:{proc.returncode}", metadata={"stderr": err})

        if not out_file.exists() or out_file.stat().st_size < 1024:
            return SynthesisResult(ok=False, engine=self.provider_id, error="kokoro_no_output")

        return SynthesisResult(
            ok=True,
            engine=self.provider_id,
            audio_path=str(out_file),
            timestamps=TimestampsPayload(text=text, words=[], sentences=[], source="local_kokoro:none"),
        )
