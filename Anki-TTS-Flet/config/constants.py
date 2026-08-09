import os
import sys
import shutil

def get_base_paths():
    """
    Determine the correct base paths for resources (read-only) and data (read-write).
    Handles both development environment and PyInstaller frozen environment.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller: Temporary folder for resources, Executable folder for data
        resource_dir = sys._MEIPASS
        exe_dir = os.path.dirname(sys.executable)
    else:
        # Development: Project root for both
        resource_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        exe_dir = resource_dir
        
    return resource_dir, exe_dir

RESOURCE_DIR, EXE_DIR = get_base_paths()

def ensure_directory(path):
    if os.path.isdir(path):
        return
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        if not os.path.isdir(path):
            raise


def resolve_data_dir():
    """Prefer %APPDATA%; fall back to a local data dir if the environment blocks it."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        preferred = os.path.join(appdata, "Anki-TTS-Edge")
        try:
            ensure_directory(preferred)
            return preferred
        except OSError:
            pass

    fallback = os.path.join(EXE_DIR, "data")
    ensure_directory(fallback)
    return fallback

# --- User Data Directory ---
# Centralize ALL user-generated files under %APPDATA%/Anki-TTS-Edge/
# Falls back to exe directory if APPDATA is not available (e.g. portable mode)
DATA_DIR = resolve_data_dir()

# Sub-directories (English names for universal compatibility)
AUDIO_DIR = os.path.join(DATA_DIR, "audio")
LOGS_DIR = os.path.join(DATA_DIR, "logs")
ensure_directory(AUDIO_DIR)
ensure_directory(LOGS_DIR)

# Backward compatibility: keep BASE_DIR pointing to DATA_DIR
BASE_DIR = DATA_DIR

# --- Migration from old paths ---
def _migrate_old_data():
    """One-time migration from old CWD-based paths to APPDATA."""
    old_audio = os.path.join(EXE_DIR, "音频")
    old_settings = os.path.join(EXE_DIR, "voice_settings.json")
    old_history = os.path.join(EXE_DIR, "history.json")
    old_voice_cache = os.path.join(EXE_DIR, "voices_cache.json")
    old_log = os.path.join(EXE_DIR, "monitor_debug.log")
    
    # Only migrate if old data exists AND we're using a different DATA_DIR
    if os.path.normpath(EXE_DIR) == os.path.normpath(DATA_DIR):
        return
    
    # Migrate audio directory
    if os.path.isdir(old_audio):
        for f in os.listdir(old_audio):
            src = os.path.join(old_audio, f)
            dst = os.path.join(AUDIO_DIR, f)
            if not os.path.exists(dst):
                try:
                    shutil.move(src, dst)
                except Exception:
                    pass
        # Remove empty old dir
        try:
            if not os.listdir(old_audio):
                os.rmdir(old_audio)
        except Exception:
            pass
    
    # Migrate individual files
    for old_file, new_file in [
        (old_settings, os.path.join(DATA_DIR, "voice_settings.json")),
        (old_history, os.path.join(DATA_DIR, "history.json")),
        (old_voice_cache, os.path.join(DATA_DIR, "voices_cache.json")),
        (old_log, os.path.join(LOGS_DIR, "monitor_debug.log")),
    ]:
        if os.path.exists(old_file) and not os.path.exists(new_file):
            try:
                shutil.move(old_file, new_file)
            except Exception:
                pass

_migrate_old_data()

# --- Assets (Read-Only → Resource Dir) ---
ASSETS_DIR = os.path.join(RESOURCE_DIR, "assets")
ICON_PATH = os.path.join(ASSETS_DIR, "icon.ico")
TRANSLATIONS_FILE = os.path.join(ASSETS_DIR, "translations.json")

# --- User Data Files ---
VOICE_CACHE_FILE = os.path.join(DATA_DIR, "voices_cache.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "voice_settings.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
LOG_FILE = os.path.join(LOGS_DIR, "monitor_debug.log")

# App Metadata
APP_VERSION = "2.9.2"
GITHUB_URL = "https://github.com/EllisMorrow/Anki-TTS-Edge"

# Default Configuration Values
DEFAULT_MAX_AUDIO_FILES = 20
DEFAULT_VOICE = "Microsoft Server Speech Text to Speech Voice (zh-CN, XiaoxiaoNeural)"
DEFAULT_APPEARANCE_MODE = "light"
DEFAULT_CUSTOM_COLOR = "#1F6AA5"
CUSTOM_WINDOW_TITLE = "Anki-TTS-Edge"

# Timeouts & Thresholds
FLOAT_WINDOW_TIMEOUT = 2
MOUSE_TIP_TIMEOUT = 1
MOUSE_DRAG_THRESHOLD = 10  # Pixels
