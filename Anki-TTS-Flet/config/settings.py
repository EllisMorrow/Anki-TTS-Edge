import json
import os
import re
from config.constants import (
    SETTINGS_FILE, DEFAULT_MAX_AUDIO_FILES, DEFAULT_VOICE,
    DEFAULT_APPEARANCE_MODE, DEFAULT_CUSTOM_COLOR
)

class SettingsManager:
    def __init__(self):
        self.settings = {}
        self.load_settings()

    def load_settings(self):
        defaults = {
            "language": "zh",
            "tts_engine": "edge_online",
            "copy_path_enabled": True,
            "autoplay_enabled": True,
            "monitor_clipboard_enabled": False,
            "monitor_selection_enabled": False,
            "minimize_to_tray": False,
            "dual_voice_mode_enabled": False,
            "selection_dual_mode_enabled": False,
            "local_engine_auto_fallback": True,
            "local_engine_download_source": "official",
            "local_engine_preferred_variant": "kokoro_int8_multi_lang_v1_1",
            "local_engine_install_dir": "",
            "local_engine_ready": False,
            "local_engine_last_healthcheck": 0,
            "local_engine_last_error": "",
            # Local Kokoro speaker IDs (sid). Keep them separate from Edge voice selection.
            "local_kokoro_sid_left": 0,
            "local_kokoro_sid_right": 0,
            "max_audio_files": DEFAULT_MAX_AUDIO_FILES,
            "selected_voice_left": DEFAULT_VOICE,
            "selected_voice_right": DEFAULT_VOICE,
            "rate": 0,
            "volume": 0,
            "appearance_mode": DEFAULT_APPEARANCE_MODE,
            "language_filter_left": "zh",
            "language_filter_right": "en",
            "custom_theme_color": DEFAULT_CUSTOM_COLOR
        }

        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                
                # Backward compatibility
                if "monitor_enabled" in loaded:
                    loaded["monitor_clipboard_enabled"] = loaded.pop("monitor_enabled")
                if "select_trigger_enabled" in loaded:
                    loaded["monitor_selection_enabled"] = loaded.pop("select_trigger_enabled")
                if "selected_voice" in loaded:
                    old_voice = loaded.pop("selected_voice")
                    loaded.setdefault("selected_voice_right", old_voice)
                    loaded.setdefault("selected_voice_left", old_voice)
                if "selected_voice_latest" in loaded and "selected_voice_right" not in loaded:
                    loaded["selected_voice_right"] = loaded.get("selected_voice_latest")
                if "selected_voice_previous" in loaded and "selected_voice_left" not in loaded:
                    loaded["selected_voice_left"] = loaded.get("selected_voice_previous")
                if "selected_voice_right" not in loaded:
                    loaded["selected_voice_right"] = loaded.get("selected_voice_left", DEFAULT_VOICE)
                if "selected_voice_left" not in loaded:
                    loaded["selected_voice_left"] = loaded.get("selected_voice_right", DEFAULT_VOICE)
                if "dual_blue_dot_enabled" in loaded:
                    legacy_dual = bool(loaded.pop("dual_blue_dot_enabled"))
                    loaded.setdefault("dual_voice_mode_enabled", legacy_dual)
                    loaded.setdefault("selection_dual_mode_enabled", legacy_dual)
                if "theme_dark" in loaded and "appearance_mode" not in loaded:
                    loaded["appearance_mode"] = "dark" if loaded.pop("theme_dark") else "light"

                self.settings = defaults.copy()
                self.settings.update(loaded)

                # Validation
                loaded_color = self.settings.get("custom_theme_color", DEFAULT_CUSTOM_COLOR)
                if not re.match(r"^#[0-9a-fA-F]{6}$", loaded_color):
                    self.settings["custom_theme_color"] = DEFAULT_CUSTOM_COLOR
                
                if self.settings.get("language") not in ["zh", "en"]:
                    self.settings["language"] = "zh"
                if self.settings.get("appearance_mode") not in ["light", "dark"]:
                    self.settings["appearance_mode"] = DEFAULT_APPEARANCE_MODE

                if not self.settings.get("selected_voice_right"):
                     self.settings["selected_voice_right"] = self.settings.get("selected_voice_left", DEFAULT_VOICE)
                if not self.settings.get("selected_voice_left"):
                     self.settings["selected_voice_left"] = self.settings.get("selected_voice_right", DEFAULT_VOICE)
                if self.settings.get("selection_dual_mode_enabled"):
                    self.settings["dual_voice_mode_enabled"] = True
                    self.settings["monitor_selection_enabled"] = True

            except Exception as e:
                print(f"Load settings failed: {e}")
                self.settings = defaults
        else:
            self.settings = defaults
        
        return self.settings

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Settings save failed: {e}")

# Global instance
settings_manager = SettingsManager()
