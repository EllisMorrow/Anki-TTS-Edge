from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from config.constants import ASSETS_DIR, DATA_DIR, ensure_directory


class LocalEngineError(RuntimeError):
    pass


@dataclass(frozen=True)
class DownloadSpec:
    asset_name: str
    urls: list[str]
    checksum_urls: list[str]


def _read_text_url(url: str, timeout: float = 20.0) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Anki-TTS-Edge"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return data.decode("utf-8", errors="replace")


def _download_file(url: str, dest_path: Path, timeout: float = 60.0) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".part")

    try:
        if tmp_path.exists():
            tmp_path.unlink()
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Anki-TTS-Edge"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp_path, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

        if dest_path.exists():
            dest_path.unlink()
        tmp_path.replace(dest_path)
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        raise


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            buf = f.read(1024 * 1024)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def _parse_checksum_txt(text: str) -> dict[str, str]:
    """
    sherpa-onnx releases provide `checksum.txt` lines:
      filename<TAB>sha256
    """
    out: dict[str, str] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        filename = parts[0].strip()
        sha256 = parts[1].strip()
        if filename and re.fullmatch(r"[0-9a-fA-F]{64}", sha256):
            out[filename] = sha256.lower()
    return out


def _safe_extract_tar_bz2(archive_path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, mode="r:*") as tf:
        target_resolved = target_dir.resolve()
        validated: list[tuple[tarfile.TarInfo, Path]] = []
        for member in tf.getmembers():
            member_name = member.name.replace("\\", "/")
            member_path = PurePosixPath(member_name)
            parts = member_path.parts
            if (
                not member_name
                or member_path.is_absolute()
                or ".." in parts
                or any(":" in part for part in parts)
            ):
                raise LocalEngineError(f"unsafe_archive_path:{member.name}")
            if not (member.isdir() or member.isreg()):
                raise LocalEngineError(f"unsafe_archive_member:{member.name}")

            dest = (target_resolved / Path(*parts)).resolve()
            try:
                common = Path(os.path.commonpath([str(target_resolved), str(dest)]))
            except ValueError:
                raise LocalEngineError(f"unsafe_archive_path:{member.name}")
            if os.path.normcase(str(common)) != os.path.normcase(str(target_resolved)):
                raise LocalEngineError(f"unsafe_archive_path:{member.name}")
            validated.append((member, dest))

        # Validate the complete member list before writing anything to disk.
        for member, dest in validated:
            if member.isdir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            source = tf.extractfile(member)
            if source is None:
                raise LocalEngineError(f"archive_read_failed:{member.name}")
            with source, open(dest, "wb") as output:
                shutil.copyfileobj(source, output)


class LocalEngineManager:
    """
    Manages local (sidecar) TTS engine installation for Kokoro via sherpa-onnx.

    V1 uses direct subprocess calls; no HTTP server.
    """

    def __init__(self, settings_manager):
        self._settings = settings_manager
        self.base_dir = self._resolve_base_dir()
        self.downloads_dir = self.base_dir / "downloads"
        self.runtime_dir = self.base_dir / "runtime"
        self.model_root_dir = self.base_dir / "model"
        self.cache_dir = self.base_dir / "cache"
        self.logs_dir = self.base_dir / "logs"
        self.manifest_path = self.base_dir / "manifest.json"
        self.install_state_path = self.base_dir / "install_state.json"
        self._ensure_dirs()

    def _resolve_base_dir(self) -> Path:
        custom = (self._settings.get("local_engine_install_dir") or "").strip()
        if custom:
            return Path(custom) / "providers" / "kokoro"
        return Path(DATA_DIR) / "providers" / "kokoro"

    def _ensure_dirs(self) -> None:
        for p in [
            self.base_dir,
            self.downloads_dir,
            self.runtime_dir,
            self.model_root_dir,
            self.cache_dir,
            self.logs_dir,
        ]:
            ensure_directory(str(p))

    def _clear_dir(self, path: Path) -> None:
        self._require_within_base(path)
        if path.is_symlink():
            path.unlink()
        elif path.exists():
            shutil.rmtree(path, ignore_errors=False)
        ensure_directory(str(path))

    def _require_within_base(self, path: Path) -> Path:
        base = self.base_dir.resolve()
        resolved = path.resolve()
        try:
            common = Path(os.path.commonpath([str(base), str(resolved)]))
        except ValueError:
            raise LocalEngineError(f"path_outside_base:{path}")
        if (
            os.path.normcase(str(common)) != os.path.normcase(str(base))
            or os.path.normcase(str(resolved)) == os.path.normcase(str(base))
        ):
            raise LocalEngineError(f"path_outside_base:{path}")
        return resolved

    def _locate_runtime_exe(self) -> Path | None:
        # The runtime package may contain multiple executables. Prefer the dedicated TTS CLI.
        patterns = [
            "**/sherpa-onnx-non-streaming-tts*.exe",
            "**/*non-streaming-tts*.exe",
            "**/*tts*.exe",
        ]
        for pat in patterns:
            hits = list(self.runtime_dir.glob(pat))
            if hits:
                hits.sort(key=lambda p: len(p.parts))
                return hits[0]
        return None

    def _install_runtime_asset(self, runtime_path: Path, asset_name: str) -> Path:
        name = str(asset_name or "").strip()
        if not name:
            raise LocalEngineError("missing_runtime_asset_name")
        lower = name.lower()

        # Always start from a clean runtime dir to avoid stale DLLs/exes across upgrades.
        self._clear_dir(self.runtime_dir)

        if lower.endswith(".exe"):
            dst = self.runtime_dir / name
            shutil.copy2(runtime_path, dst)
            return dst

        if lower.endswith(".tar.bz2") or lower.endswith(".tbz2") or lower.endswith(".tar.gz") or lower.endswith(".tgz"):
            _safe_extract_tar_bz2(runtime_path, self.runtime_dir)
            exe = self._locate_runtime_exe()
            if not exe:
                raise LocalEngineError("runtime_extract_failed")
            return exe

        raise LocalEngineError(f"unsupported_runtime_asset:{name}")

    def _load_default_manifest(self) -> dict[str, Any]:
        asset_path = Path(ASSETS_DIR) / "kokoro_manifest.json"
        if asset_path.exists():
            with open(asset_path, "r", encoding="utf-8") as f:
                return json.load(f)
        raise LocalEngineError("missing_default_manifest")

    def load_manifest(self) -> dict[str, Any]:
        default_manifest = self._load_default_manifest()

        # Download URLs, archive names, and resource layout are a trust boundary.
        # The persisted copy is informational only and must never override the
        # manifest shipped with the application.
        try:
            with open(self.manifest_path, "w", encoding="utf-8") as f:
                json.dump(default_manifest, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return default_manifest

    def _select_variant(self, manifest: dict[str, Any]) -> dict[str, Any]:
        requested = self._settings.get("local_engine_preferred_variant") or ""
        requested = str(requested).strip()
        default_id = str(manifest.get("default_variant") or "").strip()
        variants = manifest.get("variants") or []
        if not isinstance(variants, list):
            raise LocalEngineError("invalid_manifest_variants")

        by_id = {str(v.get("id")): v for v in variants if isinstance(v, dict)}
        if requested and requested in by_id:
            return by_id[requested]
        if default_id and default_id in by_id:
            return by_id[default_id]
        if by_id:
            return next(iter(by_id.values()))
        raise LocalEngineError("no_variants")

    def _build_download_spec(self, node: dict[str, Any], source_preference: str) -> DownloadSpec:
        asset_name = str(node.get("asset_name") or "").strip()
        if not asset_name:
            raise LocalEngineError("missing_asset_name")

        sources = node.get("sources") or {}
        if not isinstance(sources, dict):
            sources = {}

        checksums = node.get("checksum") or {}
        if not isinstance(checksums, dict):
            checksums = {}

        def _urls_from_sources(key: str) -> list[str]:
            v = sources.get(key)
            if isinstance(v, str) and v.strip():
                return [v.strip()]
            if isinstance(v, list):
                return [str(x).strip() for x in v if str(x).strip()]
            return []

        def _urls_from_checksums(key: str) -> list[str]:
            v = checksums.get(key)
            if isinstance(v, str) and v.strip():
                return [v.strip()]
            if isinstance(v, list):
                return [str(x).strip() for x in v if str(x).strip()]
            return []

        primary = source_preference if source_preference in ("official", "mirror") else "official"
        secondary = "mirror" if primary == "official" else "official"

        urls = _urls_from_sources(primary) + _urls_from_sources(secondary)
        checksum_urls = _urls_from_checksums(primary) + _urls_from_checksums(secondary)

        if not urls:
            raise LocalEngineError("no_download_urls")
        if not checksum_urls:
            raise LocalEngineError("no_checksum_urls")

        return DownloadSpec(asset_name=asset_name, urls=urls, checksum_urls=checksum_urls)

    def _expected_sha256(self, checksum_urls: list[str], asset_name: str) -> str:
        last_error = None
        for url in checksum_urls:
            try:
                text = _read_text_url(url)
                mapping = _parse_checksum_txt(text)
                if asset_name in mapping:
                    return mapping[asset_name]
            except Exception as ex:
                last_error = ex
                continue
        raise LocalEngineError(f"checksum_not_found:{asset_name}:{last_error}")

    def _ensure_downloaded(self, spec: DownloadSpec) -> tuple[Path, str]:
        expected = self._expected_sha256(spec.checksum_urls, spec.asset_name)
        if not re.fullmatch(r"[0-9a-fA-F]{64}", expected or ""):
            raise LocalEngineError("invalid_sha256")
        if Path(spec.asset_name).name != spec.asset_name or "/" in spec.asset_name or "\\" in spec.asset_name:
            raise LocalEngineError("invalid_asset_name")
        dest = self.downloads_dir / spec.asset_name

        if dest.exists():
            try:
                actual = _sha256_file(dest)
                if actual.lower() == expected.lower():
                    return dest, expected
                dest.unlink()
            except Exception:
                try:
                    dest.unlink()
                except Exception:
                    pass

        last_error = None
        for url in spec.urls:
            try:
                _download_file(url, dest)
                actual = _sha256_file(dest)
                if actual.lower() != expected.lower():
                    dest.unlink(missing_ok=True)
                    raise LocalEngineError("sha256_mismatch")
                return dest, expected
            except Exception as ex:
                last_error = ex
                continue

        raise LocalEngineError(f"download_failed:{spec.asset_name}:{last_error}")

    def get_status(self) -> dict[str, Any]:
        state = {}
        if self.install_state_path.exists():
            try:
                with open(self.install_state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except Exception:
                state = {}

        state.setdefault("base_dir", str(self.base_dir))
        state.setdefault("ready", bool(self._settings.get("local_engine_ready", False)))
        state.setdefault("last_error", self._settings.get("local_engine_last_error", ""))
        return state

    def is_installed(self) -> bool:
        return self.validate_installation().get("ok", False)

    def validate_installation(self) -> dict[str, Any]:
        state = {"ok": False, "error": "", "runtime_exe": "", "model_dir": "", "model_onnx": ""}
        try:
            install = self._load_install_state()
            runtime_exe = self._resolve_runtime_exe(install)
            model_dir = self._resolve_model_dir(install)
            state["runtime_exe"] = str(runtime_exe) if runtime_exe else ""
            state["model_dir"] = str(model_dir) if model_dir else ""
            if not runtime_exe or not runtime_exe.exists():
                state["error"] = "missing_runtime"
                return state
            if not model_dir:
                state["error"] = "missing_model"
                return state

            model_onnx = self._resolve_model_onnx_path(model_dir)
            state["model_onnx"] = str(model_onnx) if model_onnx else ""
            if not model_onnx or not model_onnx.exists():
                state["error"] = "missing_model_file:model*.onnx"
                return state

            required = [
                model_dir / "voices.bin",
                model_dir / "tokens.txt",
            ]
            for p in required:
                if not p.exists():
                    state["error"] = f"missing_model_file:{p.name}"
                    return state
            state["ok"] = True
            return state
        except Exception as ex:
            state["error"] = str(ex)
            return state

    def install_default(self) -> dict[str, Any]:
        manifest = self.load_manifest()
        variant = self._select_variant(manifest)
        source_preference = str(self._settings.get("local_engine_download_source", "official") or "official")

        runtime_spec = self._build_download_spec(variant.get("runtime") or {}, source_preference)
        model_spec = self._build_download_spec(variant.get("model") or {}, source_preference)

        runtime_path, runtime_sha = self._ensure_downloaded(runtime_spec)
        model_path, model_sha = self._ensure_downloaded(model_spec)

        # Prepare clean install directories after downloads succeeded.
        self._clear_dir(self.model_root_dir)
        self._clear_dir(self.cache_dir)

        runtime_exe = self._install_runtime_asset(runtime_path, runtime_spec.asset_name)

        # Extract model archive to model root (safe extraction).
        _safe_extract_tar_bz2(model_path, self.model_root_dir)

        model_dir = self._locate_kokoro_model_dir()
        if not model_dir:
            raise LocalEngineError("model_extract_failed")

        install_state = {
            "variant_id": str(variant.get("id") or ""),
            "installed_at": time.time(),
            "runtime": {
                "asset_name": runtime_spec.asset_name,
                "sha256": runtime_sha,
                "path": str(runtime_exe),
            },
            "model": {
                "asset_name": model_spec.asset_name,
                "sha256": model_sha,
                "model_dir": str(model_dir),
            },
        }
        self._save_install_state(install_state)

        health = self.healthcheck()
        return {"ok": True, "install_state": install_state, "healthcheck": health}

    def _load_install_state(self) -> dict[str, Any]:
        if not self.install_state_path.exists():
            return {}
        with open(self.install_state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}

    def _save_install_state(self, state: dict[str, Any]) -> None:
        with open(self.install_state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _resolve_runtime_exe(self, install_state: dict[str, Any]) -> Path | None:
        runtime = install_state.get("runtime") if isinstance(install_state, dict) else None
        if isinstance(runtime, dict) and runtime.get("path"):
            p = Path(str(runtime["path"]))
            if p.exists():
                return p
        return self._locate_runtime_exe()

    def _locate_kokoro_model_dir(self) -> Path | None:
        # Model filename differs across variants, e.g. `model.int8.onnx`.
        hits = list(self.model_root_dir.glob("**/model.onnx"))
        if not hits:
            hits = list(self.model_root_dir.glob("**/model.int8.onnx"))
        if not hits:
            hits = list(self.model_root_dir.glob("**/model*.onnx"))
        if not hits:
            return None
        # Prefer the shortest path (closest to root).
        hits.sort(key=lambda p: len(p.parts))
        return hits[0].parent

    def _resolve_model_onnx_path(self, model_dir: Path) -> Path | None:
        candidates = [
            model_dir / "model.onnx",
            model_dir / "model.int8.onnx",
        ]
        for p in candidates:
            if p.exists():
                return p

        hits = sorted(model_dir.glob("model*.onnx"))
        if hits:
            return hits[0]
        hits = sorted(model_dir.glob("*.onnx"))
        if hits:
            return hits[0]
        return None

    def _resolve_model_dir(self, install_state: dict[str, Any]) -> Path | None:
        model = install_state.get("model") if isinstance(install_state, dict) else None
        if isinstance(model, dict) and model.get("model_dir"):
            p = Path(str(model["model_dir"]))
            if p.exists():
                return p
        return self._locate_kokoro_model_dir()

    def healthcheck(self) -> dict[str, Any]:
        validation = self.validate_installation()
        if not validation.get("ok"):
            self._mark_not_ready(validation.get("error", "invalid_install"))
            return {"ok": False, "error": validation.get("error", "invalid_install")}

        runtime_exe = Path(validation["runtime_exe"])
        model_dir = Path(validation["model_dir"])
        model_onnx = Path(validation["model_onnx"]) if validation.get("model_onnx") else (model_dir / "model.onnx")
        out_path = self.cache_dir / "kokoro_healthcheck.wav"
        try:
            if out_path.exists():
                out_path.unlink()
        except Exception:
            pass

        cmd = [
            str(runtime_exe),
            f"--kokoro-model={model_onnx}",
            f"--kokoro-voices={model_dir / 'voices.bin'}",
            f"--kokoro-tokens={model_dir / 'tokens.txt'}",
        ]

        # Optional resources.
        espeak_dir = model_dir / "espeak-ng-data"
        if espeak_dir.exists():
            cmd.append(f"--kokoro-data-dir={espeak_dir}")
        lex_en = model_dir / "lexicon-us-en.txt"
        lex_zh = model_dir / "lexicon-zh.txt"
        if lex_en.exists() and lex_zh.exists():
            cmd.append(f"--kokoro-lexicon={lex_en},{lex_zh}")

        cmd.append(f"--output-filename={out_path}")
        cmd.append("--sid=0")
        cmd.append("hello world")

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                cwd=str(self.base_dir),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except Exception as ex:
            self._mark_not_ready(str(ex))
            return {"ok": False, "error": str(ex)}

        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()[:2000]
            self._mark_not_ready(f"tts_failed:{proc.returncode}:{err}")
            return {"ok": False, "error": f"tts_failed:{proc.returncode}", "stderr": err}

        if not out_path.exists() or out_path.stat().st_size < 1024:
            self._mark_not_ready("tts_no_output")
            return {"ok": False, "error": "tts_no_output"}

        self._mark_ready()
        return {"ok": True, "output": str(out_path)}

    def _mark_ready(self) -> None:
        self._settings.set("local_engine_ready", True)
        self._settings.set("local_engine_last_error", "")
        self._settings.set("local_engine_last_healthcheck", time.time())
        self._settings.save_settings()

    def _mark_not_ready(self, error: str) -> None:
        self._settings.set("local_engine_ready", False)
        self._settings.set("local_engine_last_error", str(error or ""))
        self._settings.set("local_engine_last_healthcheck", time.time())
        self._settings.save_settings()

    def uninstall(self) -> dict[str, Any]:
        errors: list[str] = []
        for p in [self.runtime_dir, self.model_root_dir, self.cache_dir, self.downloads_dir]:
            try:
                self._require_within_base(p)
                if p.is_symlink():
                    p.unlink()
                elif p.exists():
                    shutil.rmtree(p, ignore_errors=False)
            except Exception as ex:
                errors.append(f"{p.name}:{ex}")

        for label, path in [("state", self.install_state_path), ("manifest", self.manifest_path)]:
            try:
                self._require_within_base(path)
                if path.exists() or path.is_symlink():
                    path.unlink()
            except Exception as ex:
                errors.append(f"{label}:{ex}")

        if errors:
            self._mark_not_ready(";".join(errors))
            return {"ok": False, "error": ";".join(errors)}

        self._mark_not_ready("")
        return {"ok": True}

    def build_manual_download_instructions(self) -> dict[str, Any]:
        manifest = self.load_manifest()
        variant = self._select_variant(manifest)
        source_preference = str(self._settings.get("local_engine_download_source", "official") or "official")
        runtime_spec = self._build_download_spec(variant.get("runtime") or {}, source_preference)
        model_spec = self._build_download_spec(variant.get("model") or {}, source_preference)

        runtime_url = runtime_spec.urls[0]
        model_url = model_spec.urls[0]
        runtime_checksum = runtime_spec.checksum_urls[0]
        model_checksum = model_spec.checksum_urls[0]

        downloads_dir = str(self.downloads_dir)
        return {
            "downloads_dir": downloads_dir,
            "runtime": {
                "url": runtime_url,
                "asset_name": runtime_spec.asset_name,
                "checksum_url": runtime_checksum,
            },
            "model": {
                "url": model_url,
                "asset_name": model_spec.asset_name,
                "checksum_url": model_checksum,
            },
            "powershell": [
                f"cd \"{downloads_dir}\"",
                f"Invoke-WebRequest -Uri \"{runtime_url}\" -OutFile \"{runtime_spec.asset_name}\"",
                f"Invoke-WebRequest -Uri \"{model_url}\" -OutFile \"{model_spec.asset_name}\"",
                "# 校验: 下载 checksum.txt 后比对 SHA256（需确保文件名一致）",
                f"Invoke-WebRequest -Uri \"{runtime_checksum}\" -OutFile \"runtime_checksum.txt\"",
                f"Invoke-WebRequest -Uri \"{model_checksum}\" -OutFile \"model_checksum.txt\"",
            ],
        }
