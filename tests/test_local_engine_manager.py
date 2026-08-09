from __future__ import annotations

import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PROJECT_DIR = Path(__file__).resolve().parents[1] / "Anki-TTS-Flet"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# Import-time data directories must never point at the developer's real APPDATA.
_IMPORT_DATA_ROOT = tempfile.TemporaryDirectory()
os.environ["APPDATA"] = _IMPORT_DATA_ROOT.name

from core.local_engine_manager import (  # noqa: E402
    LocalEngineError,
    LocalEngineManager,
    _download_file,
    _parse_checksum_txt,
    _safe_extract_tar_bz2,
)


class FakeSettings:
    def __init__(self, install_root: Path):
        self.values = {"local_engine_install_dir": str(install_root)}
        self.save_count = 0

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def save_settings(self):
        self.save_count += 1


def _write_tar(path: Path, members: list[tuple[tarfile.TarInfo, bytes]]) -> None:
    with tarfile.open(path, "w:bz2") as tf:
        for info, data in members:
            if info.isreg():
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
            else:
                tf.addfile(info)


class SafeExtractionTests(unittest.TestCase):
    def test_extracts_regular_files_and_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "valid.tar.bz2"
            directory = tarfile.TarInfo("model")
            directory.type = tarfile.DIRTYPE
            file_info = tarfile.TarInfo("model/model.onnx")
            _write_tar(archive, [(directory, b""), (file_info, b"model")])

            target = root / "out"
            _safe_extract_tar_bz2(archive, target)

            self.assertEqual((target / "model" / "model.onnx").read_bytes(), b"model")

    def test_rejects_unsafe_paths_before_writing(self):
        unsafe_names = ["../escape.txt", "/absolute.txt", "C:/drive.txt", "safe/../../escape.txt"]
        for unsafe_name in unsafe_names:
            with self.subTest(name=unsafe_name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                archive = root / "unsafe.tar.bz2"
                safe = tarfile.TarInfo("safe.txt")
                unsafe = tarfile.TarInfo(unsafe_name)
                _write_tar(archive, [(safe, b"safe"), (unsafe, b"bad")])

                target = root / "out"
                with self.assertRaises(LocalEngineError):
                    _safe_extract_tar_bz2(archive, target)
                self.assertFalse((target / "safe.txt").exists())

    def test_rejects_links_devices_and_fifo(self):
        member_types = [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.FIFOTYPE]
        for member_type in member_types:
            with self.subTest(member_type=member_type), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                archive = root / "unsafe-member.tar.bz2"
                info = tarfile.TarInfo("unsafe")
                info.type = member_type
                if member_type in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                    info.linkname = "outside"
                _write_tar(archive, [(info, b"")])

                with self.assertRaises(LocalEngineError):
                    _safe_extract_tar_bz2(archive, root / "out")


class DownloadIntegrityTests(unittest.TestCase):
    def test_checksum_parser_accepts_only_exact_sha256_hex(self):
        valid = "a" * 64
        parsed = _parse_checksum_txt(
            "\n".join(
                [
                    f"valid.tar.bz2 {valid}",
                    f"too-long.tar.bz2 {valid}00",
                    f"bad-char.tar.bz2 {'g' * 64}",
                    "too-short.tar.bz2 1234",
                ]
            )
        )
        self.assertEqual(parsed, {"valid.tar.bz2": valid})

    def test_failed_download_removes_partial_file(self):
        class FailingResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, _size):
                if not hasattr(self, "already_read"):
                    self.already_read = True
                    return b"partial"
                raise OSError("connection lost")

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "runtime.tar.bz2"
            with mock.patch("core.local_engine_manager.urllib.request.urlopen", return_value=FailingResponse()):
                with self.assertRaises(OSError):
                    _download_file("https://example.invalid/runtime", dest)
            self.assertFalse(dest.exists())
            self.assertFalse(Path(str(dest) + ".part").exists())


class ManifestAndUninstallTests(unittest.TestCase):
    def test_persisted_manifest_cannot_override_bundled_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = LocalEngineManager(FakeSettings(Path(tmp)))
            manager.manifest_path.write_text(
                json.dumps(
                    {
                        "provider": "local_kokoro",
                        "version": "9999",
                        "default_variant": "malicious",
                        "variants": [
                            {
                                "id": "malicious",
                                "runtime": {"asset_name": "payload.exe", "sources": {"official": "https://evil.invalid"}},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            loaded = manager.load_manifest()
            persisted = json.loads(manager.manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(loaded, persisted)
            self.assertEqual(loaded["default_variant"], "kokoro_int8_multi_lang_v1_1")
            self.assertNotIn("evil.invalid", json.dumps(loaded))

    def test_uninstall_removes_runtime_model_cache_downloads_and_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = FakeSettings(Path(tmp))
            manager = LocalEngineManager(settings)
            for directory in [manager.runtime_dir, manager.model_root_dir, manager.cache_dir, manager.downloads_dir]:
                (directory / "artifact.bin").write_bytes(b"data")
            manager.install_state_path.write_text("{}", encoding="utf-8")
            manager.manifest_path.write_text("{}", encoding="utf-8")

            result = manager.uninstall()

            self.assertTrue(result["ok"])
            for directory in [manager.runtime_dir, manager.model_root_dir, manager.cache_dir, manager.downloads_dir]:
                self.assertFalse(directory.exists())
            self.assertFalse(manager.install_state_path.exists())
            self.assertFalse(manager.manifest_path.exists())
            self.assertFalse(settings.values["local_engine_ready"])

    def test_uninstall_refuses_a_path_outside_base(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            manager = LocalEngineManager(FakeSettings(Path(tmp)))
            outside = Path(outside_tmp) / "runtime"
            outside.mkdir()
            (outside / "keep.bin").write_bytes(b"keep")
            manager.runtime_dir = outside

            result = manager.uninstall()

            self.assertFalse(result["ok"])
            self.assertTrue((outside / "keep.bin").exists())
            self.assertIn("path_outside_base", result["error"])


if __name__ == "__main__":
    unittest.main()
