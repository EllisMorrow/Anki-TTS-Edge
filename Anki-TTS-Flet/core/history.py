import json
import os
import tempfile
import time
from config.constants import HISTORY_FILE, AUDIO_DIR
from config.settings import settings_manager

class HistoryManager:
    def __init__(self):
        self.history_file = HISTORY_FILE
        self.records = []
        self.load_records()

    def load_records(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, list):
                    normalized = []
                    for record in loaded:
                        normalized_record = self._normalize_record(record)
                        if normalized_record:
                            normalized.append(normalized_record)
                    self.records = normalized
                else:
                    self.records = []
            except Exception as e:
                print(f"Failed to load history: {e}")
                self.records = []
        else:
            self.records = []

    def save_records(self):
        try:
            directory = os.path.dirname(os.path.abspath(self.history_file))
            os.makedirs(directory, exist_ok=True)
            fd, temporary_path = tempfile.mkstemp(prefix=".history-", suffix=".tmp", dir=directory)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self.records, f, ensure_ascii=False, indent=4)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temporary_path, self.history_file)
            except Exception:
                try:
                    os.unlink(temporary_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            print(f"Failed to save history: {e}")

    def add_record(self, text, voice, path):
        """
        Add a new record to the history.
        Removes oldest records if count exceeds max_audio_files.
        """
        self.records = [record for record in self.records if record.get("path") != path]
        record = {
            "text": text,
            "voice": voice,
            "path": path,
            "timestamp": time.time()
        }
        
        # Insert at the beginning (newest first)
        self.records.insert(0, record)
        
        # Enforce limit
        try:
             max_files = int(settings_manager.get("max_audio_files", 20))
        except (ValueError, TypeError):
             max_files = 20
        max_files = max(1, max_files)

        if len(self.records) > max_files:
            overflow_records = self.records[max_files:]
            self.records = self.records[:max_files]
            for overflow_record in overflow_records:
                self._delete_associated_files(overflow_record.get("path"))
            
        self.save_records()

    def remove_record(self, record):
        if not isinstance(record, dict):
            return

        target = None
        if record in self.records:
            target = record
        else:
            target_path = record.get("path")
            target_timestamp = record.get("timestamp") or record.get("time")
            for existing in self.records:
                if target_path and existing.get("path") == target_path:
                    target = existing
                    break
                if target_timestamp and existing.get("timestamp") == target_timestamp and existing.get("text") == record.get("text"):
                    target = existing
                    break

        if target:
            path = target.get("path")
            self._delete_associated_files(path)
            self.records.remove(target)
            self.save_records()

    def get_records(self):
        return self.records

    def _normalize_record(self, record):
        if not isinstance(record, dict):
            return None

        return {
            "text": record.get("text", ""),
            "voice": record.get("voice") or record.get("voice_key") or "",
            "path": record.get("path"),
            "timestamp": record.get("timestamp") or record.get("time") or time.time(),
        }

    def clear_records(self):
        print(f"DEBUG: Clearing {len(self.records)} records...")
        count = 0
        for record in self.records:
            path = record.get("path")
            if self._delete_associated_files(path):
                count += 1
                
        print(f"DEBUG: Cleared {count} tracked audio files.")
        self.records = []
        self.save_records()
        
        # New Feature: Deep Clean Orphans
        self._deep_clean_audio_dir()

    def _deep_clean_audio_dir(self):
        """Scan AUDIO_DIR and remove all app-generated files"""
        if not os.path.exists(AUDIO_DIR): return
        
        print(f"DEBUG: Deep cleaning {AUDIO_DIR}")
        orphan_count = 0
        try:
            for filename in os.listdir(AUDIO_DIR):
                file_path = self._resolve_audio_path(filename)
                is_app_file = (
                    file_path
                    and filename.startswith("Anki-TTS-Edge_")
                    and filename.endswith((".mp3", ".wav", ".json", ".timestamps.json"))
                )

                if is_app_file and os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                        orphan_count += 1
                        print(f"DEBUG: Removed orphan: {filename}")
                    except Exception as e:
                        print(f"Error removing orphan {filename}: {e}")
            
            print(f"DEBUG: Removed {orphan_count} orphaned files.")
            
        except Exception as e:
            print(f"Error during deep clean: {e}")

    def _delete_associated_files(self, path):
        """Helper to delete audio file and its metadata (timestamps)"""
        audio_path = self._resolve_audio_path(path)
        if not audio_path:
            return False
        
        success = False
        # Delete Audio
        if os.path.isfile(audio_path):
            try:
                os.remove(audio_path)
                success = True
            except Exception as e:
                print(f"Error removing audio file {audio_path}: {e}")
        
        # Delete Timestamps if exists 
        # Pattern 1: [filename].json (Old/Standard)
        # Pattern 2: [filename].timestamps.json (New/Observed)
        
        base_path = os.path.splitext(audio_path)[0]
        potential_json_paths = [
            base_path + ".json",
            base_path + ".timestamps.json"
        ]
        
        for json_path in potential_json_paths:
            if self._is_in_audio_dir(json_path) and os.path.isfile(json_path):
                 try:
                     os.remove(json_path)
                     print(f"DEBUG: Removed metadata: {json_path}")
                 except Exception as e:
                     print(f"Error removing metadata {json_path}: {e}")
                 
        return success

    @staticmethod
    def _is_in_audio_dir(path):
        """Return whether a path resolves inside AUDIO_DIR, rejecting traversal and links."""
        try:
            audio_root = os.path.realpath(os.path.abspath(AUDIO_DIR))
            candidate = os.path.realpath(os.path.abspath(path))
            return os.path.commonpath((audio_root, candidate)) == audio_root
        except (TypeError, ValueError):
            return False

    def _resolve_audio_path(self, path):
        """Resolve legacy absolute or relative history paths without crossing AUDIO_DIR."""
        if not isinstance(path, (str, os.PathLike)) or not path:
            return None
        candidate = os.fspath(path)
        if not os.path.isabs(candidate):
            candidate = os.path.join(AUDIO_DIR, candidate)
        return os.path.abspath(candidate) if self._is_in_audio_dir(candidate) else None

history_manager = HistoryManager()
