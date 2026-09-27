import json
import os
import re
import tempfile
from config.constants import (
    SETTINGS_FILE, DEFAULT_MAX_AUDIO_FILES, DEFAULT_VOICE,
    DEFAULT_APPEARANCE_MODE, DEFAULT_CUSTOM_COLOR
)
from config.ui_scale import DEFAULT_UI_SCALE_PERCENT, normalize_ui_scale_percent

EDGE_VOICE_NAME_PATTERN = re.compile(
    r"^Microsoft Server Speech Text to Speech Voice \([a-z]{2,3}-"
    r"(?:[A-Z][a-z]{3}-)?(?:[A-Z]{2}|[0-9]{3})(?:-[A-Za-z]+)?, .*Neural\)$"
)
KOKORO_FAVORITE_PATTERN = re.compile(r"^local_kokoro:v1_1:(0|[1-9][0-9]{0,2})$")


def is_valid_voice_favorite_key(key):
    if not isinstance(key, str):
        return False
    if key.startswith("edge_online:"):
        return bool(EDGE_VOICE_NAME_PATTERN.fullmatch(key[len("edge_online:"):]))
    match = KOKORO_FAVORITE_PATTERN.fullmatch(key)
    return bool(match and int(match.group(1)) <= 102)


def voice_favorite_key(engine, voice):
    """Identify a voice independently of the left/right UI slot."""
    if engine == "edge_online":
        name = voice.get("name") if isinstance(voice, dict) else voice
        key = f"edge_online:{name}" if isinstance(name, str) else None
    elif engine == "local_kokoro":
        sid = voice.get("sid") if isinstance(voice, dict) else voice
        if isinstance(sid, bool):
            return None
        try:
            number = int(sid)
        except (TypeError, ValueError, OverflowError):
            return None
        if str(sid) != str(number):
            return None
        key = f"local_kokoro:v1_1:{number}"
    else:
        return None
    return key if is_valid_voice_favorite_key(key) else None


def normalize_voice_favorites(value):
    if not isinstance(value, list):
        return []
    return sorted({key for key in value if is_valid_voice_favorite_key(key)})


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
            # When dual voice mode is disabled, which slot ("left"/"right") the single-generate button uses.
            # Default to "right" to preserve legacy behavior.
            "single_voice_active_slot": "right",
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
            "voice_favorites": [],
            "max_audio_files": DEFAULT_MAX_AUDIO_FILES,
            "selected_voice_left": DEFAULT_VOICE,
            "selected_voice_right": DEFAULT_VOICE,
            "rate": 0,
            "volume": 0,
            "appearance_mode": DEFAULT_APPEARANCE_MODE,
            "ui_scale_percent": DEFAULT_UI_SCALE_PERCENT,
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
                self.settings["voice_favorites"] = normalize_voice_favorites(
                    self.settings.get("voice_favorites")
                )

                # Validation
                loaded_color = self.settings.get("custom_theme_color", DEFAULT_CUSTOM_COLOR)
                if not re.match(r"^#[0-9a-fA-F]{6}$", loaded_color):
                    self.settings["custom_theme_color"] = DEFAULT_CUSTOM_COLOR
                
                if self.settings.get("language") not in ["zh", "en"]:
                    self.settings["language"] = "zh"
                if self.settings.get("appearance_mode") not in ["light", "dark"]:
                    self.settings["appearance_mode"] = DEFAULT_APPEARANCE_MODE
                self.settings["ui_scale_percent"] = normalize_ui_scale_percent(
                    self.settings.get("ui_scale_percent")
                )

                if not self.settings.get("selected_voice_right"):
                     self.settings["selected_voice_right"] = self.settings.get("selected_voice_left", DEFAULT_VOICE)
                if not self.settings.get("selected_voice_left"):
                     self.settings["selected_voice_left"] = self.settings.get("selected_voice_right", DEFAULT_VOICE)

                active_slot = str(self.settings.get("single_voice_active_slot", "right") or "right").strip().lower()
                if active_slot not in ("left", "right"):
                    self.settings["single_voice_active_slot"] = "right"
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
        if key == "ui_scale_percent":
            value = normalize_ui_scale_percent(value)
        elif key == "voice_favorites":
            value = normalize_voice_favorites(value)
        self.settings[key] = value

    def get_voice_favorites(self):
        return set(normalize_voice_favorites(self.settings.get("voice_favorites")))

    def is_voice_favorite(self, engine, voice):
        key = voice_favorite_key(engine, voice)
        return key is not None and key in self.get_voice_favorites()

    def set_voice_favorite(self, engine, voice, favorite):
        key = voice_favorite_key(engine, voice)
        return self.set_voice_favorite_key(key, favorite)

    def set_voice_favorite_key(self, key, favorite):
        """Persist a favorite; restore the previous in-memory value on write failure."""
        if not is_valid_voice_favorite_key(key) or not isinstance(favorite, bool):
            return False
        previous = self.get_voice_favorites()
        updated = previous.copy()
        if favorite:
            updated.add(key)
        else:
            updated.discard(key)
        if updated == previous:
            return True
        self.settings["voice_favorites"] = sorted(updated)
        if self.save_settings():
            return True
        self.settings["voice_favorites"] = sorted(previous)
        return False

    def reconcile_edge_favorites(self, voices):
        """Prune missing Edge voices only after a complete, validated network catalog."""
        if not isinstance(voices, list) or not voices:
            return False
        available = set()
        for voice in voices:
            if not isinstance(voice, dict):
                return False
            key = voice_favorite_key("edge_online", voice)
            if key is None or key in available:
                return False
            available.add(key)
        previous = self.get_voice_favorites()
        updated = {key for key in previous if not key.startswith("edge_online:") or key in available}
        if updated == previous:
            return True
        self.settings["voice_favorites"] = sorted(updated)
        if self.save_settings():
            return True
        self.settings["voice_favorites"] = sorted(previous)
        return False

    def save_settings(self):
        try:
            self.settings["ui_scale_percent"] = normalize_ui_scale_percent(
                self.settings.get("ui_scale_percent")
            )
            self.settings["voice_favorites"] = normalize_voice_favorites(
                self.settings.get("voice_favorites")
            )
            directory = os.path.dirname(os.path.abspath(SETTINGS_FILE))
            os.makedirs(directory, exist_ok=True)
            fd, temporary_path = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=directory)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self.settings, f, ensure_ascii=False, indent=4)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temporary_path, SETTINGS_FILE)
                return True
            except Exception:
                try:
                    os.unlink(temporary_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            print(f"Settings save failed: {e}")
            return False

# Global instance
settings_manager = SettingsManager()
