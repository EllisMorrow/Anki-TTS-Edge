import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


APP_ROOT = Path(__file__).resolve().parents[1] / "Anki-TTS-Flet"
SETTINGS_MODULE_PATH = APP_ROOT / "config" / "settings.py"
VOICES_MODULE_PATH = APP_ROOT / "core" / "voices.py"
EDGE_A = "Microsoft Server Speech Text to Speech Voice (zh-CN, XiaoxiaoNeural)"
EDGE_B = "Microsoft Server Speech Text to Speech Voice (en-US, JennyNeural)"
EDGE_SCRIPT_LOCALE = "Microsoft Server Speech Text to Speech Voice (iu-Latn-CA, SiqiniqNeural)"


def load_settings_module(settings_file):
    config = types.ModuleType("config")
    config.__path__ = [str(APP_ROOT / "config")]
    constants = types.ModuleType("config.constants")
    constants.SETTINGS_FILE = str(settings_file)
    constants.DEFAULT_MAX_AUDIO_FILES = 20
    constants.DEFAULT_VOICE = EDGE_A
    constants.DEFAULT_APPEARANCE_MODE = "light"
    constants.DEFAULT_CUSTOM_COLOR = "#1F6AA5"
    spec = importlib.util.spec_from_file_location("favorites_settings_under_test", SETTINGS_MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {"config": config, "config.constants": constants}):
        spec.loader.exec_module(module)
    return module


class VoiceFavoritesTests(unittest.TestCase):
    def setUp(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.settings_file = Path(temporary_directory.name) / "settings.json"
        self.module = load_settings_module(self.settings_file)
        self.manager = self.module.SettingsManager()

    def test_shared_keys_and_persistence_across_manager_reload(self):
        edge_key = f"edge_online:{EDGE_A}"
        kokoro_key = "local_kokoro:v1_1:0"
        self.assertEqual(self.module.voice_favorite_key("local_kokoro", {"sid": 0}), kokoro_key)
        self.assertTrue(self.manager.set_voice_favorite_key(edge_key, True))
        self.assertTrue(self.manager.set_voice_favorite("local_kokoro", {"sid": 0}, True))
        reloaded = self.module.SettingsManager()
        self.assertEqual(reloaded.get_voice_favorites(), {edge_key, kokoro_key})
        self.assertTrue(reloaded.is_voice_favorite("edge_online", EDGE_A))
        self.assertTrue(reloaded.set_voice_favorite_key(edge_key, False))
        self.assertEqual(self.module.SettingsManager().get_voice_favorites(), {kokoro_key})

    def test_script_locale_voice_can_be_favorited(self):
        key = f"edge_online:{EDGE_SCRIPT_LOCALE}"
        self.assertTrue(self.manager.set_voice_favorite_key(key, True))
        self.assertIn(key, self.module.SettingsManager().get_voice_favorites())

    def test_malformed_saved_favorites_are_discarded(self):
        good_key = f"edge_online:{EDGE_A}"
        self.settings_file.write_text(json.dumps({"voice_favorites": [good_key, good_key, 1, {},
            "local_kokoro:v1_1:103", "edge_online:", "local_kokoro:v1_1:true"]}), encoding="utf-8")
        self.assertEqual(self.module.SettingsManager().get_voice_favorites(), {good_key})
        self.assertFalse(self.manager.set_voice_favorite_key("local_kokoro:v1_1:103", True))
        self.assertFalse(self.manager.set_voice_favorite("local_kokoro", True, True))
        self.assertFalse(self.manager.set_voice_favorite_key(good_key, "yes"))

    def test_failed_save_restores_in_memory_favorites_and_existing_file(self):
        edge_key = f"edge_online:{EDGE_A}"
        self.assertTrue(self.manager.set_voice_favorite_key(edge_key, True))
        original = self.settings_file.read_bytes()
        with mock.patch.object(self.module.os, "replace", side_effect=OSError("disk failure")):
            self.assertFalse(self.manager.set_voice_favorite_key(edge_key, False))
        self.assertEqual(self.manager.get_voice_favorites(), {edge_key})
        self.assertEqual(self.settings_file.read_bytes(), original)

    def test_reconcile_requires_valid_nonempty_catalog_and_preserves_kokoro(self):
        edge_a = f"edge_online:{EDGE_A}"
        edge_b = f"edge_online:{EDGE_B}"
        kokoro = "local_kokoro:v1_1:0"
        self.manager.set("voice_favorites", [edge_a, edge_b, kokoro])
        self.assertTrue(self.manager.save_settings())
        for catalog in ([], [{}], [{"name": "bad"}], [{"name": EDGE_A}, {"name": EDGE_A}]):
            self.assertFalse(self.manager.reconcile_edge_favorites(catalog))
            self.assertEqual(self.manager.get_voice_favorites(), {edge_a, edge_b, kokoro})
        self.assertTrue(self.manager.reconcile_edge_favorites([{"name": EDGE_A}]))
        self.assertEqual(self.manager.get_voice_favorites(), {edge_a, kokoro})


class VoiceFetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_bad_network_data_does_not_replace_cache(self):
        edge_tts = types.ModuleType("edge_tts")
        voice_manager = mock.Mock()
        voice_manager.find.return_value = [{"Name": EDGE_A}, {"Name": "unexpected format"}]
        edge_tts.VoicesManager = types.SimpleNamespace(create=mock.AsyncMock(return_value=voice_manager))
        i18n_module = types.ModuleType("utils.i18n")
        i18n_module.i18n = types.SimpleNamespace(get=lambda *args: "ok")
        voice_db = types.ModuleType("core.voice_db")
        voice_db.save_voice_cache = mock.Mock()
        voice_db.load_voice_cache = mock.Mock(return_value=[])
        spec = importlib.util.spec_from_file_location("voices_under_test", VOICES_MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"edge_tts": edge_tts, "utils.i18n": i18n_module,
                                      "core.voice_db": voice_db}):
            spec.loader.exec_module(module)
        self.assertEqual(await module.fetch_voices_from_network(), [])
        voice_db.save_voice_cache.assert_not_called()
        voice_manager.find.return_value = []
        self.assertEqual(await module.fetch_voices_from_network(), [])
        voice_db.save_voice_cache.assert_not_called()
        voice_manager.find.return_value = [{"Name": EDGE_A}]
        self.assertEqual([v["name"] for v in await module.fetch_voices_from_network()], [EDGE_A])
        voice_db.save_voice_cache.assert_called_once()

        voice_db.save_voice_cache.reset_mock()
        voice_manager.find.return_value = [{"Name": EDGE_SCRIPT_LOCALE}]
        self.assertEqual(
            [v["name"] for v in await module.fetch_voices_from_network()],
            [EDGE_SCRIPT_LOCALE],
        )
        voice_db.save_voice_cache.assert_called_once()


if __name__ == "__main__":
    unittest.main()
