import threading
from PIL import Image
import pystray
import os
from config.constants import ICON_PATH
from utils.i18n import i18n

class TrayIconManager:
    def __init__(self, on_show_hide=None, on_exit=None):
        self.icon_instance = None
        self.tray_thread = None
        self.on_show_hide = on_show_hide
        self.on_exit = on_exit
        self.image = None
        self._setup_complete = False

    def setup(self):
        if self._setup_complete:
            return

        try:
            print(f"DEBUG: Loading tray icon from {ICON_PATH}")
            if os.path.exists(ICON_PATH):
                try:
                    with Image.open(ICON_PATH) as image:
                        # Keep decoded pixels after closing the icon file.
                        self.image = image.convert("RGBA")
                except Exception as load_err:
                    print(f"ERROR: PIL failed to open {ICON_PATH}: {load_err}")
                    raise load_err
            else:
                raise FileNotFoundError(f"Icon not found at {ICON_PATH}")
        except Exception as e:
            print(f"Error loading tray icon (General): {e}. Generating fallback.")
            # Generate a simple blue square icon
            self.image = Image.new('RGB', (64, 64), color=(0, 128, 255))
        
        # Ensure image is valid before creating Icon
        if not self.image:
             self.image = Image.new('RGB', (64, 64), color=(255, 0, 0)) # Red fallback

        menu = (
            pystray.MenuItem(i18n.get("tray_show_hide", "Show/Hide"), self._on_show_hide_click, default=True),
            pystray.MenuItem(i18n.get("tray_exit", "Exit"), self._on_exit_click)
        )

        self.icon_instance = pystray.Icon(
            "AnkiTTS",
            self.image,
            i18n.get("window_title", "Anki-TTS"),
            menu=menu
        )
        self._setup_complete = True

    def start(self):
        if not self._setup_complete:
            self.setup()
        
        if self.tray_thread and self.tray_thread.is_alive():
            return

        def run_icon():
            try:
                print("Starting tray icon...")
                self.icon_instance.run()
                print("Tray icon stopped.")
            except Exception as e:
                print(f"Error running tray icon: {e}")

        self.tray_thread = threading.Thread(target=run_icon, daemon=True)
        self.tray_thread.start()

    def stop(self):
        if self.icon_instance:
            self.icon_instance.stop()

    def _on_show_hide_click(self, icon, item):
        if self.on_show_hide:
            self.on_show_hide()

    def _on_exit_click(self, icon, item):
        if self.on_exit:
            self.on_exit()
