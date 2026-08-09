from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1] / "Anki-TTS-Flet"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# Isolate config.constants before importing the provider.
_IMPORT_DATA_ROOT = tempfile.TemporaryDirectory()
os.environ["APPDATA"] = _IMPORT_DATA_ROOT.name

from core.tts_local_kokoro_provider import LocalKokoroProvider  # noqa: E402
from core.tts_types import SynthesisRequest  # noqa: E402


class KokoroCacheIdentityTests(unittest.TestCase):
    def test_rate_volume_and_pitch_are_part_of_cache_identity(self):
        provider = LocalKokoroProvider.__new__(LocalKokoroProvider)
        base = SynthesisRequest(text="hello", voice="edge-fallback", speaker_id=1)
        rate = SynthesisRequest(text="hello", voice="edge-fallback", speaker_id=1, rate="+10%")
        volume = SynthesisRequest(text="hello", voice="edge-fallback", speaker_id=1, volume="-10%")
        pitch = SynthesisRequest(text="hello", voice="edge-fallback", speaker_id=1, pitch="+5Hz")

        paths = {
            provider._build_output_path(request, 1)
            for request in [base, rate, volume, pitch]
        }

        self.assertEqual(len(paths), 4)


if __name__ == "__main__":
    unittest.main()
