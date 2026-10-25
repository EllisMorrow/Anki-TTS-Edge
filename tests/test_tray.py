import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


APP_ROOT = Path(__file__).resolve().parents[1] / "Anki-TTS-Flet"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from core.tray import TrayIconManager


class TrayImageTests(unittest.TestCase):
    @patch("core.tray.pystray.Icon")
    def test_bundled_icon_decodes_and_setup_is_idempotent(self, icon_class):
        manager = TrayIconManager()
        handles = []
        open_image = Image.open

        def track_open(*args, **kwargs):
            image = open_image(*args, **kwargs)
            handles.append(image.fp)
            return image

        with patch("core.tray.Image.open", side_effect=track_open):
            manager.setup()
            manager.setup()

        self.assertTrue(manager._setup_complete)
        self.assertIsInstance(manager.image, Image.Image)
        self.assertEqual(manager.image.mode, "RGBA")
        self.assertGreater(manager.image.width, 0)
        self.assertGreater(manager.image.height, 0)
        self.assertEqual(len(handles), 1)
        self.assertTrue(handles[0].closed)
        icon_class.assert_called_once()
        self.assertIs(icon_class.call_args.args[1], manager.image)

    @patch("core.tray.pystray.Icon")
    def test_missing_or_invalid_icon_uses_fallback(self, icon_class):
        with tempfile.TemporaryDirectory() as temp_dir:
            icon_path = Path(temp_dir) / "icon.ico"
            for content in (None, b"invalid image"):
                with self.subTest(content=content):
                    if content is not None:
                        icon_path.write_bytes(content)
                    with patch("core.tray.ICON_PATH", str(icon_path)):
                        manager = TrayIconManager()
                        manager.setup()
                    self.assertTrue(manager._setup_complete)
                    self.assertEqual(manager.image.size, (64, 64))
                    self.assertEqual(manager.image.getpixel((0, 0)), (0, 128, 255))
                    self.assertIs(icon_class.call_args.args[1], manager.image)


if __name__ == "__main__":
    unittest.main()
