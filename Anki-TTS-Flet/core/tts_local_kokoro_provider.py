from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import threading
from pathlib import Path

from config.constants import AUDIO_DIR
from core.local_engine_manager import LocalEngineManager
from core.kokoro_voice_catalog import kokoro_v1_1_sid_to_name
from core.tts_provider import TTSProvider
from core.tts_types import SynthesisRequest, SynthesisResult, TimestampsPayload
from utils.text import sanitize_text

logger = logging.getLogger(__name__)


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
        self._active_proc = None
        self._active_proc_lock = threading.Lock()

    async def cancel_active(self, reason: str = "shutdown", wait_timeout_s: float = 2.0) -> bool:
        """Best-effort kill for the currently running Kokoro child process (if any)."""
        proc = None
        with self._active_proc_lock:
            proc = self._active_proc

        if not proc or getattr(proc, "returncode", None) is not None:
            return False

        try:
            proc.kill()
        except Exception:
            return False

        try:
            await asyncio.wait_for(proc.wait(), timeout=wait_timeout_s)
        except Exception:
            pass

        logger.info("Killed active Kokoro process due to %s", reason)
        return True

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
                # sherpa-onnx's Kokoro CLI does not expose Edge-compatible
                # volume/pitch controls. Keep requested adjustments in the cache
                # identity so a changed request can never reuse stale audio.
                "rate": request.rate or "+0%",
                "volume": request.volume or "+0%",
                "pitch": request.pitch or "+0Hz",
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

        sid = 0
        try:
            if request.speaker_id is not None:
                sid = int(request.speaker_id)
        except Exception:
            sid = 0
        sid = max(0, sid)

        out_path = request.output_path or self._build_output_path(request, sid)
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        if out_file.exists() and out_file.stat().st_size > 1024:
            speaker_name = kokoro_v1_1_sid_to_name(sid) or ""
            return SynthesisResult(
                ok=True,
                engine=self.provider_id,
                audio_path=str(out_file),
                timestamps=TimestampsPayload(text=text, words=[], sentences=[], source="local_kokoro:none"),
                metadata={"cache_hit": True, "speaker_id": sid, "speaker_name": speaker_name},
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

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._engine.base_dir),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            with self._active_proc_lock:
                self._active_proc = proc

            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=120.0)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    await proc.wait()
                except Exception:
                    pass
                return SynthesisResult(
                    ok=False,
                    engine=self.provider_id,
                    error="kokoro_timeout",
                    metadata={"speaker_id": sid, "speaker_name": kokoro_v1_1_sid_to_name(sid) or ""},
                )
            except asyncio.CancelledError:
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    await proc.wait()
                except Exception:
                    pass
                return SynthesisResult(
                    ok=False,
                    engine=self.provider_id,
                    error="kokoro_cancelled",
                    metadata={"speaker_id": sid, "speaker_name": kokoro_v1_1_sid_to_name(sid) or ""},
                )
        except Exception as ex:
            return SynthesisResult(ok=False, engine=self.provider_id, error=str(ex))
        finally:
            with self._active_proc_lock:
                if self._active_proc is proc:
                    self._active_proc = None

        rc = getattr(proc, "returncode", None)
        if rc != 0:
            try:
                stdout = (stdout_b or b"").decode("utf-8", errors="replace")
            except Exception:
                stdout = ""
            try:
                stderr = (stderr_b or b"").decode("utf-8", errors="replace")
            except Exception:
                stderr = ""

            stdout_snip = (stdout or "").strip()[:2000]
            stderr_snip = (stderr or "").strip()[:2000]
            if stderr_snip:
                logger.warning("Kokoro failed rc=%s stderr=%s", rc, stderr_snip[:300])
            elif stdout_snip:
                logger.warning("Kokoro failed rc=%s stdout=%s", rc, stdout_snip[:300])

            return SynthesisResult(
                ok=False,
                engine=self.provider_id,
                error=f"kokoro_failed:{rc}",
                metadata={
                    "stdout": stdout_snip,
                    "stderr": stderr_snip,
                    "speaker_id": sid,
                    "speaker_name": kokoro_v1_1_sid_to_name(sid) or "",
                },
            )

        if not out_file.exists() or out_file.stat().st_size < 1024:
            return SynthesisResult(ok=False, engine=self.provider_id, error="kokoro_no_output", metadata={"speaker_id": sid})

        speaker_name = kokoro_v1_1_sid_to_name(sid) or ""
        return SynthesisResult(
            ok=True,
            engine=self.provider_id,
            audio_path=str(out_file),
            timestamps=TimestampsPayload(text=text, words=[], sentences=[], source="local_kokoro:none"),
            metadata={"speaker_id": sid, "speaker_name": speaker_name},
        )
