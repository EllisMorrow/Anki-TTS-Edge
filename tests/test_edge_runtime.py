import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
import types
import unittest
from pathlib import Path
from unittest import mock


APP_ROOT = Path(__file__).resolve().parents[1] / "Anki-TTS-Flet"
RUNTIME_PATH = APP_ROOT / "core" / "edge_runtime.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EdgeStartupTests(unittest.TestCase):
    def test_importing_main_does_not_import_edge_tts(self):
        legacy_names = (
            "音频", "voice_settings.json", "history.json",
            "voices_cache.json", "monitor_debug.log",
        )
        existing = [name for name in legacy_names if (APP_ROOT / name).exists()]
        if existing:
            self.skipTest(f"Avoid importing config while legacy user data exists: {existing}")

        script = textwrap.dedent("""
            import importlib.abc
            import sys
            from pathlib import Path
            from unittest import mock

            app_root = Path(sys.argv[1])
            legacy_names = (
                "音频", "voice_settings.json", "history.json",
                "voices_cache.json", "monitor_debug.log",
            )
            # config.constants migrates these paths at import time. Refuse to
            # import it if user data appeared after the parent's preflight.
            assert not any((app_root / name).exists() for name in legacy_names)
            sys.path.insert(0, str(app_root))

            class RejectEdgeTts(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname == "edge_tts" or fullname.startswith("edge_tts."):
                        raise AssertionError("Startup imported edge_tts: " + fullname)
                    return None

            sys.meta_path.insert(0, RejectEdgeTts())
            import flet
            with mock.patch.object(flet, "app", side_effect=AssertionError("GUI launch")):
                import main
            assert callable(main.main)
            assert not any(name == "edge_tts" or name.startswith("edge_tts.")
                           for name in sys.modules)
            print("main-imported-without-edge-tts")
        """)
        with tempfile.TemporaryDirectory() as temporary_directory:
            environment = {**os.environ, "APPDATA": temporary_directory}
            result = subprocess.run(
                [sys.executable, "-B", "-X", "utf8", "-I", "-c", script, str(APP_ROOT)],
                cwd=temporary_directory,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("main-imported-without-edge-tts", result.stdout)


class EdgeRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_import_runs_in_worker_while_event_loop_can_continue(self):
        runtime = load_module("edge_runtime_under_test", RUNTIME_PATH)
        edge_tts = types.ModuleType("edge_tts")
        loop = asyncio.get_running_loop()
        loop_thread = threading.get_ident()
        started = asyncio.Event()
        release = threading.Event()
        import_threads = []

        def import_edge_tts(name):
            import_threads.append(threading.get_ident())
            loop.call_soon_threadsafe(started.set)
            if not release.wait(timeout=5):
                raise TimeoutError("The event loop did not resume during import")
            return edge_tts

        with mock.patch.object(runtime.importlib, "import_module", side_effect=import_edge_tts) as importer:
            task = asyncio.create_task(runtime.load_edge_tts())
            try:
                await asyncio.wait_for(started.wait(), timeout=2)
                self.assertFalse(task.done())
                self.assertEqual(len(import_threads), 1)
                self.assertNotEqual(import_threads[0], loop_thread)
            finally:
                release.set()
                result = await task
            self.assertIs(result, edge_tts)
            importer.assert_called_once_with("edge_tts")

    async def test_failed_import_propagates_and_can_be_retried(self):
        runtime = load_module("edge_runtime_under_test", RUNTIME_PATH)
        failure = ModuleNotFoundError("edge_tts dependency unavailable")
        edge_tts = types.ModuleType("edge_tts")
        with mock.patch.object(runtime.importlib, "import_module", side_effect=[failure, edge_tts]) as importer:
            with self.assertRaises(ModuleNotFoundError) as raised:
                await runtime.load_edge_tts()
            self.assertIs(raised.exception, failure)
            self.assertIs(await runtime.load_edge_tts(), edge_tts)
            self.assertEqual(importer.call_args_list, [mock.call("edge_tts"), mock.call("edge_tts")])

    async def test_audio_generation_keeps_parameters_audio_and_timestamps(self):
        runtime = load_module("edge_runtime_under_test", RUNTIME_PATH)
        edge_tts = types.ModuleType("edge_tts")

        class Communication:
            async def stream(self):
                yield {"type": "audio", "data": b"first"}
                yield {"type": "WordBoundary", "text": "Hello", "offset": 1_000_000,
                       "duration": 2_500_000}
                yield {"type": "audio", "data": b"second"}

        edge_tts.Communicate = mock.Mock(return_value=Communication())
        i18n_module = types.ModuleType("utils.i18n")
        i18n_module.i18n = types.SimpleNamespace(get=lambda key, *args, **kwargs: key)

        with tempfile.TemporaryDirectory() as temporary_directory:
            constants = types.ModuleType("config.constants")
            constants.AUDIO_DIR = temporary_directory
            modules = {"config.constants": constants, "utils.i18n": i18n_module,
                       "core.edge_runtime": runtime, "edge_tts": edge_tts}
            with mock.patch.dict(sys.modules, modules), mock.patch.object(sys, "path", [str(APP_ROOT), *sys.path]):
                audio_gen = load_module("audio_generation_under_test", APP_ROOT / "core" / "audio_gen.py")
                output_path = str(Path(temporary_directory) / "sample.mp3")
                result_path, timestamps = await audio_gen.generate_audio_with_timestamps_async(
                    "Hello.", "en-US-JennyNeural", "+10%", "-5%", "+2Hz", output_path
                )

            edge_tts.Communicate.assert_called_once_with(
                "Hello.", "en-US-JennyNeural", rate="+10%", volume="-5%", pitch="+2Hz",
                boundary="WordBoundary",
            )
            self.assertEqual(result_path, output_path)
            self.assertEqual(Path(output_path).read_bytes(), b"firstsecond")
            self.assertEqual(timestamps["text"], "Hello.")
            self.assertEqual(timestamps["words"][0]["text"], "Hello")
            self.assertEqual(timestamps["words"][0]["start_ms"], 100)
            self.assertEqual(timestamps["words"][0]["end_ms"], 350)
            self.assertEqual(timestamps["sentences"][0]["text"], "Hello.")
            saved = json.loads(Path(output_path.replace(".mp3", ".timestamps.json")).read_text(encoding="utf-8"))
            self.assertEqual(saved, timestamps)


if __name__ == "__main__":
    unittest.main()
