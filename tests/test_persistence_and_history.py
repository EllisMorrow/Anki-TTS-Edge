import atexit
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / "Anki-TTS-Flet"
sys.path.insert(0, str(APP_ROOT))
_original_appdata = os.environ.get("APPDATA")
_isolated_appdata = tempfile.TemporaryDirectory()
os.environ["APPDATA"] = _isolated_appdata.name


@atexit.register
def _restore_appdata():
    if _original_appdata is None:
        os.environ.pop("APPDATA", None)
    else:
        os.environ["APPDATA"] = _original_appdata
    _isolated_appdata.cleanup()


class PersistenceAndHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temporary_directory.name)
        self.audio_dir = self.data_dir / "audio"
        self.audio_dir.mkdir()

        # Constants are module globals, so patch them after import instead of
        # reading any real application data from APPDATA.
        self.history = importlib.import_module("core.history")
        self.settings = importlib.import_module("config.settings")
        self.voice_db = importlib.import_module("core.voice_db")
        self.history.AUDIO_DIR = str(self.audio_dir)
        self.history.HISTORY_FILE = str(self.data_dir / "history.json")
        self.settings.SETTINGS_FILE = str(self.data_dir / "voice_settings.json")
        self.voice_db.VOICE_CACHE_FILE = str(self.data_dir / "voices_cache.json")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_history_never_deletes_outside_audio_directory(self):
        outside_file = self.data_dir / "keep-me.mp3"
        outside_file.write_bytes(b"outside")
        manager = self.history.HistoryManager()
        manager.records = [{"text": "bad", "voice": "v", "path": str(outside_file), "timestamp": 1}]

        manager.remove_record(manager.records[0])

        self.assertTrue(outside_file.exists())
        self.assertEqual(manager.records, [])

    def test_history_allows_legacy_relative_paths_inside_audio_directory(self):
        audio_file = self.audio_dir / "legacy.mp3"
        metadata_file = self.audio_dir / "legacy.timestamps.json"
        audio_file.write_bytes(b"audio")
        metadata_file.write_text("{}", encoding="utf-8")
        manager = self.history.HistoryManager()
        record = {"text": "ok", "voice": "v", "path": "legacy.mp3", "timestamp": 1}
        manager.records = [record]

        manager.remove_record(record)

        self.assertFalse(audio_file.exists())
        self.assertFalse(metadata_file.exists())

    def test_deep_clean_removes_generated_wav_and_leaves_user_files(self):
        generated = [
            "Anki-TTS-Edge_online_hash.mp3",
            "Anki-TTS-Edge_kokoro_sid0_hash.wav",
            "Anki-TTS-Edge_online_hash.timestamps.json",
        ]
        for name in generated:
            (self.audio_dir / name).write_text("generated", encoding="utf-8")
        user_file = self.audio_dir / "my-recording.wav"
        user_file.write_text("user", encoding="utf-8")

        self.history.HistoryManager()._deep_clean_audio_dir()

        self.assertFalse(any((self.audio_dir / name).exists() for name in generated))
        self.assertTrue(user_file.exists())

    def test_atomic_saves_replace_complete_files(self):
        history_manager = self.history.HistoryManager()
        history_manager.records = [{"text": "x", "voice": "v", "path": "x.mp3", "timestamp": 1}]
        history_manager.save_records()
        self.assertEqual(json.loads(Path(self.history.HISTORY_FILE).read_text(encoding="utf-8"))[0]["text"], "x")

        settings_manager = self.settings.SettingsManager()
        settings_manager.settings = {"language": "en"}
        settings_manager.save_settings()
        self.assertEqual(json.loads(Path(self.settings.SETTINGS_FILE).read_text(encoding="utf-8"))["language"], "en")

        self.voice_db.save_voice_cache({"voice": "cached"})
        self.assertEqual(json.loads(Path(self.voice_db.VOICE_CACHE_FILE).read_text(encoding="utf-8"))["voice"], "cached")

    def test_failed_replace_preserves_existing_file(self):
        targets = [
            (self.history, "HISTORY_FILE", lambda: self.history.HistoryManager().save_records()),
            (self.settings, "SETTINGS_FILE", lambda: self.settings.SettingsManager().save_settings()),
            (self.voice_db, "VOICE_CACHE_FILE", lambda: self.voice_db.save_voice_cache({"new": True})),
        ]
        for module, attribute, save in targets:
            target = Path(getattr(module, attribute))
            target.write_text('{"old": true}', encoding="utf-8")
            with mock.patch.object(module.os, "replace", side_effect=OSError("replace failed")):
                save()
            self.assertEqual(target.read_text(encoding="utf-8"), '{"old": true}')
            self.assertEqual(list(target.parent.glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
