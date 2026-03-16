import flet as ft
from utils.i18n import i18n
import threading
import ctypes
import asyncio
import inspect
import re
import time
from config.constants import CUSTOM_WINDOW_TITLE, ICON_PATH, APP_VERSION, DEFAULT_VOICE
from ui.home_view import HomeView
from core.voices import get_cached_voices, fetch_voices_from_network
from ui.history_view import HistoryView
from ui.settings_view import SettingsView
from core.audio_gen import load_timestamps
from core.history import history_manager
from config.settings import settings_manager
from core.tts_manager import TTSManager
from core.tts_types import SynthesisRequest
from datetime import datetime
import os
import pygame
from core.files import copy_file_to_clipboard
from core.clipboard import MonitorManager
from core.tray import TrayIconManager
from core.local_engine_manager import LocalEngineManager
import logging
import multiprocessing

# Load saved language setting before UI initialization
saved_language = settings_manager.get("language", "zh")
i18n.set_language(saved_language)

async def main(page: ft.Page):
    async def maybe_await(result):
        if inspect.isawaitable(result):
            await result

    # 1. Page Configuration
    page.title = f"{CUSTOM_WINDOW_TITLE} v{APP_VERSION}"
    
    # Load Window Dimensions (Default: 750x850)
    saved_width = settings_manager.get("window_width", 750)
    saved_height = settings_manager.get("window_height", 850)
    
    # Ensure integer conversion (settings might store as string)
    try:
        saved_width = int(saved_width) if saved_width else 750
        saved_height = int(saved_height) if saved_height else 850
    except (ValueError, TypeError):
        saved_width, saved_height = 750, 850
    
    print(f"DEBUG: Loading window size: {saved_width}x{saved_height}")
    
    # Set window size BEFORE showing (prevents flash)
    page.window.width = saved_width
    page.window.height = saved_height
    page.window.min_width = 400
    page.window.min_height = 500
    page.padding = 0
    page.spacing = 0
    
    # Set window icon (same as tray icon)
    page.window.icon = ICON_PATH
    
    # Center window on screen
    await maybe_await(page.window.center())
    
    # Note: handle_resize will be defined and bound later after settings_view is created
    
    # Theme — keep custom palette, but tolerate older Flet ColorScheme fields in packaged builds.
    def create_compatible_color_scheme(**kwargs):
        filtered_kwargs = dict(kwargs)
        while True:
            try:
                return ft.ColorScheme(**filtered_kwargs)
            except TypeError as exc:
                match = re.search(r"unexpected keyword argument '([^']+)'", str(exc))
                if not match:
                    raise
                unsupported_key = match.group(1)
                if unsupported_key not in filtered_kwargs:
                    raise
                filtered_kwargs.pop(unsupported_key)

    page.theme = ft.Theme(
        color_scheme_seed="#475569",
        color_scheme=create_compatible_color_scheme(
            primary="#475569",                   # Slate-600: neutral, professional
            on_primary="#FFFFFF",
            primary_container="#E2E8F0",         # Slate-200: soft container
            on_primary_container="#1E293B",       # Slate-800: readable text
            secondary="#64748B",                  # Slate-500: muted accent
            secondary_container="#F1F5F9",        # Slate-100
            surface="#FAFAFA",                    # Neutral white
            on_surface="#1E293B",                 # Slate-800
            surface_variant="#F1F5F9",            # Slate-100
            outline="#94A3B8",                    # Slate-400
        ),
    )
    page.dark_theme = ft.Theme(
        color_scheme_seed="#94A3B8",
        color_scheme=create_compatible_color_scheme(
            primary="#94A3B8",                    # Slate-400
            on_primary="#0F172A",                 # Slate-900
            primary_container="#334155",           # Slate-700
            on_primary_container="#CBD5E1",        # Slate-300
            secondary="#64748B",                   # Slate-500
            secondary_container="#1E293B",         # Slate-800
            surface="#1E293B",                     # Slate-800
            on_surface="#E2E8F0",                  # Slate-200
            surface_variant="#334155",             # Slate-700
            outline="#64748B",                     # Slate-500
            background="#0F172A",                  # Slate-900
        ),
    )
    page.theme_mode = (
        ft.ThemeMode.DARK
        if settings_manager.get("appearance_mode", "light") == "dark"
        else ft.ThemeMode.LIGHT
    )
    
    
    # Helper for Snackbar (Flet 0.21+ compatibility)
    def show_message(msg, is_error=False):
        color = ft.Colors.RED if is_error else ft.Colors.GREEN
        page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=color)
        page.snack_bar.open = True
        page.update()

    # Helper functions removed


    # 2. Top Navigation
    # Create views first so we can switch them in place.
    home_view = HomeView(page)
    history_view = HistoryView(page)
    settings_view = SettingsView(page)
    local_engine_manager = LocalEngineManager(settings_manager)
    
    nav_state = {"index": 0}
    nav_items = []
    tab_specs = [
        {
            "label_key": "tab_voices",
            "fallback": "合成",
            "icon": ft.Icons.RECORD_VOICE_OVER,
            "view": home_view,
        },
        {
            "label_key": "history_panel_title",
            "fallback": "历史",
            "icon": ft.Icons.HISTORY,
            "view": history_view,
        },
        {
            "label_key": "tab_settings",
            "fallback": "设置",
            "icon": ft.Icons.SETTINGS,
            "view": settings_view,
        },
    ]

    def refresh_navigation_styles():
        is_dark = page.theme_mode == ft.ThemeMode.DARK
        active_text = "#E2E8F0" if is_dark else "#1E293B"
        inactive_text = "#94A3B8" if is_dark else "#64748B"
        active_bg = "#334155" if is_dark else "#E2E8F0"

        for index, spec in enumerate(tab_specs):
            is_active = nav_state["index"] == index
            spec["icon_control"].color = active_text if is_active else inactive_text
            spec["label_control"].color = active_text if is_active else inactive_text
            spec["label_control"].weight = "w700" if is_active else "w600"
            spec["nav_item"].bgcolor = active_bg if is_active else None

    def set_active_view(index, should_update=True):
        nav_state["index"] = index
        view_host.content = tab_specs[index]["view"]
        refresh_navigation_styles()
        if should_update:
            navigation_bar.update()
            view_host.update()

    for index, spec in enumerate(tab_specs):
        spec["icon_control"] = ft.Icon(spec["icon"], size=18)
        spec["label_control"] = ft.Text(
            i18n.get(spec["label_key"], spec["fallback"]),
            size=11,
            weight="w600",
        )
        spec["nav_item"] = ft.Container(
            content=ft.Row(
                [
                    spec["icon_control"],
                    spec["label_control"],
                ],
                spacing=4,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(vertical=4, horizontal=10),
            border_radius=6,
            ink=True,
            on_click=lambda e, idx=index: set_active_view(idx),
        )
        nav_items.append(spec["nav_item"])

    view_host = ft.Container(content=home_view, expand=True)
    navigation_bar = ft.Container(
        content=ft.Row(nav_items, spacing=8, alignment=ft.MainAxisAlignment.START),
        padding=ft.padding.symmetric(horizontal=12, vertical=6),
    )
    main_layout = ft.Column(
        [
            navigation_bar,
            ft.Divider(height=1),
            view_host,
        ],
        expand=True,
        spacing=0,
    )
    refresh_navigation_styles()

    # Language change handler - refresh UI text
    def handle_language_change(new_lang):
        """Refresh UI elements when language changes"""
        print(f"DEBUG: Language changed to {new_lang}, refreshing UI...")
        
        for spec in tab_specs:
            spec["label_control"].value = i18n.get(spec["label_key"], spec["fallback"])
        
        # Update page title
        page.title = f"{CUSTOM_WINDOW_TITLE} v{APP_VERSION}"
        home_view.refresh_texts()
        history_view.refresh_texts()
        settings_view.refresh_texts()
        refresh_local_engine_status_ui()

        refresh_navigation_styles()
        navigation_bar.update()
        view_host.update()
    
    settings_view.on_language_changed = handle_language_change
    monitor_manager = None
    tray_manager = None

    def refresh_local_engine_status_ui():
        try:
            settings_view.update_local_engine_status(settings_manager.settings, base_dir=str(local_engine_manager.base_dir))
        except Exception as ex:
            print(f"DEBUG: local engine status ui refresh failed: {ex}")

    def handle_local_engine_open_dir():
        try:
            if os.name == "nt":
                os.startfile(str(local_engine_manager.base_dir))
        except Exception as ex:
            show_message(f"Open engine dir failed: {ex}", True)

    def handle_local_engine_manual_instructions():
        return local_engine_manager.build_manual_download_instructions()

    def handle_local_engine_install_clicked():
        async def _task():
            settings_view.set_local_engine_busy(True, i18n.get("local_engine_busy_installing"))
            try:
                result = await asyncio.to_thread(local_engine_manager.install_default)
            except Exception as ex:
                result = {"ok": False, "error": str(ex)}
            finally:
                settings_view.set_local_engine_busy(False)
                refresh_local_engine_status_ui()

            if result.get("ok"):
                health = result.get("healthcheck") if isinstance(result, dict) else None
                if isinstance(health, dict) and health.get("ok"):
                    show_message("离线引擎安装完成")
                else:
                    show_message(f"离线引擎安装完成，但校验失败: {(health or {}).get('error') if isinstance(health, dict) else 'unknown'}", True)
            else:
                show_message(f"离线引擎安装失败: {result.get('error')}", True)

        page.run_task(_task)

    def handle_local_engine_healthcheck_clicked():
        async def _task():
            settings_view.set_local_engine_busy(True, i18n.get("local_engine_busy_checking"))
            try:
                result = await asyncio.to_thread(local_engine_manager.healthcheck)
            except Exception as ex:
                result = {"ok": False, "error": str(ex)}
            finally:
                settings_view.set_local_engine_busy(False)
                refresh_local_engine_status_ui()

            if result.get("ok"):
                show_message("离线引擎可用")
            else:
                show_message(f"离线引擎不可用: {result.get('error')}", True)

        page.run_task(_task)

    def handle_local_engine_uninstall_clicked():
        async def _task():
            settings_view.set_local_engine_busy(True, i18n.get("local_engine_busy_uninstalling"))
            try:
                result = await asyncio.to_thread(local_engine_manager.uninstall)
            except Exception as ex:
                result = {"ok": False, "error": str(ex)}
            finally:
                settings_view.set_local_engine_busy(False)
                refresh_local_engine_status_ui()

            if result.get("ok"):
                show_message("离线引擎已卸载")
            else:
                show_message(f"离线引擎卸载失败: {result.get('error')}", True)

        page.run_task(_task)

    settings_view.on_local_engine_install = handle_local_engine_install_clicked
    settings_view.on_local_engine_healthcheck = handle_local_engine_healthcheck_clicked
    settings_view.on_local_engine_uninstall = handle_local_engine_uninstall_clicked
    settings_view.on_local_engine_manual_instructions = handle_local_engine_manual_instructions
    settings_view.on_local_engine_open_dir = handle_local_engine_open_dir

    async def restore_main_window():
        page.window.minimized = False
        page.window.visible = True
        await maybe_await(page.window.to_front())
        page.update()

    async def destroy_main_window():
        if monitor_manager:
            monitor_manager.stop_monitors()
        if tray_manager:
            tray_manager.stop()
        await maybe_await(page.window.destroy())
    
    # Restart cleanup handler - stop tray and monitors before restart
    def handle_app_restart():
        print("DEBUG: Cleanup before restart...")
        if monitor_manager:
            monitor_manager.stop()
        if tray_manager:
            tray_manager.stop()
    
    settings_view.on_app_restart = handle_app_restart
    
    # Window resize handler - debounced to avoid per-frame disk writes during drag
    _resize_timer = {"task": None}
    
    def handle_resize(e):
        new_width = int(page.window.width) if page.window.width else 750
        new_height = int(page.window.height) if page.window.height else 850
        # Sync UI display immediately (cheap)
        settings_view.update_window_size_display(new_width, new_height)
        
        # Debounce disk write: cancel previous timer, start new 300ms delay
        async def _save_after_delay():
            await asyncio.sleep(0.3)
            settings_manager.set("window_width", new_width)
            settings_manager.set("window_height", new_height)
            settings_manager.save_settings()
        
        if _resize_timer["task"]:
            _resize_timer["task"].cancel()
        _resize_timer["task"] = page.run_task(_save_after_delay)
        
    page.on_resized = handle_resize
    
    # Handle when user changes size in settings UI
    def handle_window_size_from_settings(width, height):
        print(f"DEBUG: User set window size to {width}x{height} in settings")
        page.window.width = width
        page.window.height = height
        settings_manager.set("window_width", width)
        settings_manager.set("window_height", height)
        settings_manager.save_settings()
        page.update()
        
    settings_view.on_window_size_change = handle_window_size_from_settings

    # 4. Main Layout
    page.add(main_layout)
    
    # Initialize Pygame Mixer early (fast operation)
    pygame.mixer.init()
    
    # Show UI immediately
    home_view.set_status("正在加载语音列表...", ft.Icons.HOURGLASS_EMPTY, ft.Colors.BLUE_100)
    page.splash = None
    page.update()

    voice_state = {"current": [], "loaded_from_cache": False}

    def voice_signature(voices):
        return tuple(v.get("name") for v in voices or [])

    # Background refresh: check network for updates
    async def background_voice_refresh():
        try:
            # Wait a bit to not slow down startup
            await asyncio.sleep(3)
            
            # Fetch fresh data
            fresh_voices = await fetch_voices_from_network()
            current_voices = voice_state["current"]
            
            # Compare with current (cache was already shown)
            if fresh_voices and voice_signature(fresh_voices) != voice_signature(current_voices):
                print(f"DEBUG: Voice list updated in background ({len(current_voices)} -> {len(fresh_voices)})")
                voice_state["current"] = fresh_voices
                home_view.populate_voices(fresh_voices)
                page.update()
        except Exception as e:
            print(f"DEBUG: Background voice refresh failed: {e}")

    async def load_initial_voices():
        try:
            cached_voices = get_cached_voices()
            voice_state["loaded_from_cache"] = bool(cached_voices)

            if cached_voices:
                voices = cached_voices
            else:
                home_view.set_status("正在联网加载语音列表...", ft.Icons.HOURGLASS_EMPTY, ft.Colors.BLUE_100)
                page.update()
                voices = await fetch_voices_from_network()

            voice_state["current"] = voices
            home_view.populate_voices(voices)
            home_view.set_status("", None, None)
            page.update()

            if voice_state["loaded_from_cache"]:
                asyncio.create_task(background_voice_refresh())
        except Exception as e:
            home_view.set_status(f"加载语音失败: {e}", ft.Icons.ERROR_OUTLINE, ft.Colors.RED_100)
            page.update()

    page.run_task(load_initial_voices)

    
    # Mini Mode Removed - Replaced by Satellite Process logic
    # (See satellite_loop below)
        # Satellite Poll Loop
    import queue

    def get_voice_for_slot(slot, fallback_to_default=True):
        key = "selected_voice_left" if slot == "left" else "selected_voice_right"
        voice = settings_manager.get(key)
        if voice:
            return voice
        return DEFAULT_VOICE if fallback_to_default else None
    
    async def handle_satellite_action(text, mode="B"):
        if not text:
            return
        print(f"Main: Received ACTION for '{text[:10]}', mode='{mode}'")
        
        home_view.set_input_text(text)
        if monitor_manager:
            monitor_manager.set_selection_overlay_active(False)
            monitor_manager.set_selection_generation_active(True)
        
        voice_slot = "right" if mode == "B" else "left"
        voice = get_voice_for_slot(voice_slot)
        
        print(f"DEBUG: Handle Action - Voice Slot: {voice_slot}, Voice: '{voice}'")

        if not voice:
            if monitor_manager:
                monitor_manager.set_selection_generation_active(False)
            show_message(i18n.get("status_no_voice_error") + f" (Mode {mode})", True)
            return
        
        try:
            monitor_manager.sat_input_q.put(("STATE", "generating"))
        except Exception:
            pass

        try:
            path, _, _ = await generate_audio_for_voice(text, voice)
            try:
                monitor_manager.sat_input_q.put(("STATE", "success" if path else "error"))
            except Exception:
                pass
        finally:
            if monitor_manager:
                monitor_manager.set_selection_generation_active(False)

    async def satellite_loop():
        # print("DEBUG: Satellite Loop Started")
        while True:
            try:
                selection_enabled = settings_manager.get("monitor_selection_enabled", False)
                sat_queue_ready = monitor_manager and hasattr(monitor_manager, 'sat_output_q') and monitor_manager.sat_output_q

                if selection_enabled and sat_queue_ready:
                    try:
                        cmd, *args = monitor_manager.sat_output_q.get_nowait()
                        if cmd == "ACTION":
                            text = args[0]
                            mode = args[1] if len(args) > 1 else "B"
                            await handle_satellite_action(text, mode=mode)
                        elif cmd == "DISMISSED":
                            if monitor_manager:
                                monitor_manager.set_selection_overlay_active(False)
                        elif cmd == "RESTORE":
                            print("Main: Restoring Window")
                            await restore_main_window()
                    except queue.Empty:
                        pass
            except Exception as e:
                print(f"DEBUG: Error in Satellite Loop: {e}")
            
            await asyncio.sleep(0.04 if settings_manager.get("monitor_selection_enabled", False) else 0.4)

    page.run_task(satellite_loop)

    # 7. Interaction Handlers
    # Playback state management
    current_audio_state = {
        "path": None,
        "timestamps": None,
        "text": None,
        "is_playing": False,
        "is_paused": False,  # Distinguish between pause and stop
        "current_sentence_index": 0,
        "current_word_index": 0,
        "text_dirty": False,  # True if user edited text after last generation
        "current_playback_start_ms": 0, # Offset to add to pygame.get_pos()
        "stop_playback_at_ms": None # If set, stop when this pos is reached
    }
    playback_monitor_state = {"run_id": 0}
    clipboard_generation_state = {"text": "", "at": 0.0}
    generation_lock = asyncio.Lock()
    tts_manager = TTSManager(settings_manager)

    def sync_home_controls(*controls):
        home_view._safe_update(*controls)

    def copy_generated_file_to_clipboard(path):
        if not path or not settings_manager.get("copy_path_enabled", True):
            return False
        try:
            if monitor_manager:
                monitor_manager.suppress_clipboard(1.2)
            copy_file_to_clipboard(path)
            return True
        except Exception as ex:
            print(f"DEBUG: copy generated file failed: {ex}")
            show_message(f"MP3 剪贴板写入失败: {ex}", True)
            return False

    def apply_generated_audio_result(text, voice, path, timestamps=None, autoplay=None):
        if not path:
            return

        home_view.set_input_text(text, mark_as_generated=True)
        home_view.set_status("音频生成成功", ft.Icons.CHECK_CIRCLE_OUTLINE, ft.Colors.GREEN_100)

        current_audio_state["path"] = path
        current_audio_state["timestamps"] = timestamps
        current_audio_state["text"] = text
        current_audio_state["text_dirty"] = False
        current_audio_state["current_sentence_index"] = 0
        current_audio_state["current_word_index"] = 0
        current_audio_state["current_playback_start_ms"] = 0
        current_audio_state["stop_playback_at_ms"] = None

        copy_generated_file_to_clipboard(path)
        history_manager.add_record(text, voice, path)
        history_view.populate_history(history_manager.get_records())

        should_autoplay = settings_manager.get("autoplay_enabled", True) if autoplay is None else autoplay
        if should_autoplay:
            handle_play_audio({"path": path, "timestamps": timestamps, "text": text})

    async def generate_audio_for_voice(text, voice, status_message="正在生成音频...", autoplay=None):
        sanitized_text = (text or "").strip()
        if not sanitized_text:
            home_view.set_status("请输入文本", ft.Icons.WARNING_AMBER, ft.Colors.ORANGE_100)
            return None, i18n.get("status_no_text_error"), None

        selected_voice = voice or DEFAULT_VOICE
        if not selected_voice:
            home_view.set_status("请选择声音", ft.Icons.WARNING_AMBER, ft.Colors.ORANGE_100)
            return None, i18n.get("status_no_voice_error"), None

        async with generation_lock:
            home_view.set_status(status_message, ft.Icons.HOURGLASS_EMPTY, ft.Colors.BLUE_100)
            try:
                request = SynthesisRequest(
                    text=sanitized_text,
                    voice=selected_voice,
                    rate=f"{int(home_view.rate_slider.value):+d}%",
                    volume=f"{int(home_view.volume_slider.value):+d}%",
                    pitch="+0Hz",
                    engine=settings_manager.get("tts_engine", "edge_online") or "edge_online",
                )
                timeout_s = 120.0 if request.engine == "local_kokoro" else 30.0
                result = await asyncio.wait_for(tts_manager.synthesize(request), timeout=timeout_s)
            except asyncio.TimeoutError:
                result = None
                path, error, timestamps = None, i18n.get("status_timeout_error", "Generation timed out"), None
            except Exception as ex:
                result = None
                path, error, timestamps = None, str(ex), None
            else:
                if result and result.ok:
                    path = result.audio_path
                    timestamps = result.timestamps.to_dict() if result.timestamps else None
                    error = None
                    fallback_from = None
                    try:
                        fallback_from = (result.metadata or {}).get("fallback_from")
                    except Exception:
                        fallback_from = None
                else:
                    path = None
                    timestamps = None
                    error = (result.error if result else None) or "unknown_error"
                    fallback_from = None

            if path:
                apply_generated_audio_result(sanitized_text, selected_voice, path, timestamps, autoplay=autoplay)
                if fallback_from:
                    show_message("本地引擎不可用，已自动回退在线模式。")
            else:
                home_view.set_status(f"生成失败: {error}", ft.Icons.ERROR_OUTLINE, ft.Colors.RED_100)
                show_message(f"Error: {error}", True)

            return path, error, timestamps

    def restart_playback_monitor():
        playback_monitor_state["run_id"] += 1
        run_id = playback_monitor_state["run_id"]

        async def _runner():
            await playback_monitor_loop(run_id)

        page.run_task(_runner)

    def cancel_playback_monitor():
        playback_monitor_state["run_id"] += 1

    async def handle_generate(e, voice):
        # Auto-clean HTML tags before processing
        home_view.clean_text_input()
        
        text = home_view.get_input_text()
        if not text:
            show_message(i18n.get("status_no_text_error"), True)
            home_view.set_status("请输入文本", ft.Icons.WARNING_AMBER, ft.Colors.ORANGE_100)
            return

        await generate_audio_for_voice(text, voice)

    async def handle_generate_b(e):
        # Latest Voice (B)
        v = get_voice_for_slot("right", fallback_to_default=False)
        if not v:
            show_message(i18n.get("status_no_voice_error"), True)
            return
        await handle_generate(e, v)

    async def handle_generate_a(e):
        # Previous Voice (A)
        v = get_voice_for_slot("left", fallback_to_default=False)
        if not v:
             show_message(i18n.get("status_no_voice_error"), True)
             return
        await handle_generate(e, v)

    # Audio Handlers
    def handle_play_audio(e):
        path = None
        timestamps = None
        text = None
        if isinstance(e, dict):
             path = e.get("path")
             timestamps = e.get("timestamps")
             text = e.get("text")
        
        if path and os.path.exists(path):
            print(f"DEBUG: Playing Audio: {path}")
            try:
                # Update status
                home_view.set_status("正在播放...", ft.Icons.PLAY_CIRCLE_OUTLINE, ft.Colors.GREEN_100)
                path_changed = current_audio_state["path"] != path
                
                # Update state
                current_audio_state["path"] = path
                current_audio_state["is_playing"] = True
                current_audio_state["is_paused"] = False
                current_audio_state["current_word_index"] = 0
                current_audio_state["current_sentence_index"] = 0
                current_audio_state["current_playback_start_ms"] = 0 # Reset offset
                current_audio_state["stop_playback_at_ms"] = None # Reset stop constraint
                if path_changed:
                    current_audio_state["timestamps"] = None
                    current_audio_state["text"] = None
                
                if timestamps:
                    current_audio_state["timestamps"] = timestamps
                elif path_changed or not current_audio_state["timestamps"]:
                    # Try to load timestamps from file
                    current_audio_state["timestamps"] = load_timestamps(path)
                
                if text:
                    current_audio_state["text"] = text
                elif current_audio_state["timestamps"] and current_audio_state["timestamps"].get("text"):
                    current_audio_state["text"] = current_audio_state["timestamps"]["text"]
                
                # Set text input to read-only during playback
                home_view.text_input.read_only = True
                
                # Show highlighted text if we have word timings
                ts = current_audio_state["timestamps"]
                if ts and ts.get("words"):
                    home_view.show_highlighted_text(
                        current_audio_state.get("text", ""),
                        ts["words"]
                    )
                
                sync_home_controls(home_view.text_input)
                
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                home_view.btn_play_pause.selected = True
                sync_home_controls(home_view.btn_play_pause)
                
                # Start playback monitoring
                restart_playback_monitor()
            except Exception as ex:
                print(f"Error playing: {ex}")
                home_view.set_status(f"播放失败: {ex}", ft.Icons.ERROR_OUTLINE, ft.Colors.RED_100)
                current_audio_state["is_playing"] = False
    
    def handle_stop_audio(e):
        pygame.mixer.music.stop()
        cancel_playback_monitor()
        current_audio_state["is_playing"] = False
        current_audio_state["is_paused"] = False
        current_audio_state["current_sentence_index"] = 0
        current_audio_state["current_word_index"] = 0
        current_audio_state["current_playback_start_ms"] = 0
        current_audio_state["stop_playback_at_ms"] = None
        home_view.btn_play_pause.selected = False
        home_view.text_input.read_only = False
        home_view.hide_highlighted_text()  # Hide highlighting
        home_view.set_status("已停止", ft.Icons.STOP_CIRCLE_OUTLINED, ft.Colors.GREY_200)
        sync_home_controls(home_view.btn_play_pause, home_view.text_input)
    
    async def handle_pause_resume(e):
        """Toggle play/pause state, or generate if no audio exists"""
        # Case 1: Currently playing -> pause
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            current_audio_state["is_paused"] = True
            home_view.btn_play_pause.selected = False
            home_view.set_status("已暂停", ft.Icons.PAUSE_CIRCLE_OUTLINE, ft.Colors.AMBER_100)
            sync_home_controls(home_view.btn_play_pause)
            return
        
        # Case 2: Paused -> resume
        if current_audio_state["is_paused"]:
            pygame.mixer.music.unpause()
            current_audio_state["is_paused"] = False
            current_audio_state["is_playing"] = True
            # Resume means continue to end, so clear any existing stop constraint
            current_audio_state["stop_playback_at_ms"] = None
            
            home_view.btn_play_pause.selected = True
            home_view.set_status("正在播放...", ft.Icons.PLAY_CIRCLE_OUTLINE, ft.Colors.GREEN_100)
            sync_home_controls(home_view.btn_play_pause)
            return
        
        # Case 3: No audio or text changed -> need to generate first
        text = home_view.get_input_text()
        if not text:
            home_view.set_status("请输入文本", ft.Icons.WARNING_AMBER, ft.Colors.ORANGE_100)
            return
        
        # Check if we have valid cached audio
        has_valid_cache = (
            current_audio_state["path"] and 
            os.path.exists(current_audio_state["path"]) and
            not home_view.is_text_dirty()
        )
        
        if has_valid_cache:
            # Play from cache
            home_view.set_status("从缓存播放...", ft.Icons.PLAY_CIRCLE_OUTLINE, ft.Colors.GREEN_100)
            handle_play_audio({
                "path": current_audio_state["path"], 
                "timestamps": current_audio_state["timestamps"]
            })
        else:
            # Need to generate first
            voice = get_voice_for_slot("right")
            await generate_audio_for_voice(text, voice, status_message="正在生成音频...", autoplay=True)
    
    def handle_replay(e):
        """Replay from beginning"""
        if current_audio_state["path"] and os.path.exists(current_audio_state["path"]):
            current_audio_state["current_sentence_index"] = 0
            handle_play_audio({"path": current_audio_state["path"], "timestamps": current_audio_state["timestamps"]})
    
    async def ensure_audio_ready(e):
        """Helper to generate audio if missing before navigation"""
        if not current_audio_state.get("timestamps"):
             # Need to generate
             v = get_voice_for_slot("right", fallback_to_default=False)
             if not v:
                 home_view.set_status("请选择声音", ft.Icons.WARNING_AMBER, ft.Colors.ORANGE_100)
                 return False
                 
             await handle_generate(e, v)
             
             # After generation, handle_generate starts playback from 0. 
             # We might intercept or just let it be, but we need timestamps now.
             if not current_audio_state.get("timestamps"):
                 return False
        return True

    async def handle_prev_sentence(e):
        """Jump to previous sentence"""
        if not await ensure_audio_ready(e): return

        timestamps = current_audio_state.get("timestamps")
        if not timestamps or not timestamps.get("sentences"):
            return
        
        sentences = timestamps["sentences"]
        current_idx = current_audio_state["current_sentence_index"]
        
        # User constraint: "只播放上一句" (Only play this sentence)
        target_idx = max(0, current_idx - 1)
        sent = sentences[target_idx]
        target_ms = sent["start_ms"]
        stop_ms = sent["end_ms"]
        
        current_audio_state["current_sentence_index"] = target_idx
        current_audio_state["current_playback_start_ms"] = target_ms 
        current_audio_state["stop_playback_at_ms"] = stop_ms 
            
        try:
            # FIX: Always use play(start=) to reset get_pos() for consistent timing offset
            pygame.mixer.music.play(start=target_ms / 1000.0)
            
            home_view.btn_play_pause.selected = True
            sync_home_controls(home_view.btn_play_pause)
            
            # FIX: Immediate Highlight Update
            first_word_idx = -1
            if timestamps.get("words"):
                 for i, w in enumerate(timestamps["words"]):
                     if w["start_ms"] >= target_ms:
                         first_word_idx = i
                         break
            if first_word_idx != -1:
                current_audio_state["current_word_index"] = first_word_idx
                home_view.update_highlight_position(first_word_idx)
            
            # Ensure loop running
            if not current_audio_state["is_playing"]:
                current_audio_state["is_playing"] = True
                restart_playback_monitor()
                
        except Exception as ex:
            print(f"DEBUG: prev failed: {ex}")
    
    async def handle_next_sentence(e):
        """Jump to next sentence"""
        if not await ensure_audio_ready(e): return
        
        timestamps = current_audio_state.get("timestamps")
        if not timestamps or not timestamps.get("sentences"):
            return
        
        sentences = timestamps["sentences"]
        current_idx = current_audio_state["current_sentence_index"]
        
        if current_idx < len(sentences) - 1:
            target_idx = current_idx + 1
            sent = sentences[target_idx]
            
            target_ms = sent["start_ms"]
            stop_ms = sent["end_ms"]
            
            current_audio_state["current_sentence_index"] = target_idx
            current_audio_state["current_playback_start_ms"] = target_ms
            current_audio_state["stop_playback_at_ms"] = stop_ms 
            
            try:
                # FIX: Always use play(start=) to reset get_pos()
                pygame.mixer.music.play(start=target_ms / 1000.0)

                home_view.btn_play_pause.selected = True
                sync_home_controls(home_view.btn_play_pause)
                
                # FIX: Immediate Highlight Update
                first_word_idx = -1
                if timestamps.get("words"):
                     for i, w in enumerate(timestamps["words"]):
                         if w["start_ms"] >= target_ms:
                             first_word_idx = i
                             break
                if first_word_idx != -1:
                    current_audio_state["current_word_index"] = first_word_idx
                    home_view.update_highlight_position(first_word_idx)
                
                if not current_audio_state["is_playing"]:
                    current_audio_state["is_playing"] = True
                    restart_playback_monitor()

            except Exception as ex:
                print(f"DEBUG: next failed: {ex}")

    def handle_word_jump(word_index):
        """Click to Play: Jump to the exact clicked word position"""
        timestamps = current_audio_state.get("timestamps")
        if not timestamps or not timestamps.get("words"): return
        
        if word_index < 0 or word_index >= len(timestamps["words"]): return
        target_word = timestamps["words"][word_index]
        word_ms = target_word["start_ms"]
        
        # Track sentence index for prev/next navigation
        sentences = timestamps.get("sentences", [])
        for i, sent in enumerate(sentences):
            if sent["start_ms"] <= word_ms < sent["end_ms"]:
                current_audio_state["current_sentence_index"] = i
                break
        
        # Play from exact word position (not sentence start)
        current_audio_state["current_playback_start_ms"] = word_ms
        current_audio_state["stop_playback_at_ms"] = None
        
        try:
            pygame.mixer.music.play(start=word_ms / 1000.0)
            
            current_audio_state["is_paused"] = False
            home_view.btn_play_pause.selected = True
            sync_home_controls(home_view.btn_play_pause)
            
            # Highlight the clicked word immediately
            current_audio_state["current_word_index"] = word_index
            home_view.update_highlight_position(word_index)
            
            if not current_audio_state["is_playing"]:
                current_audio_state["is_playing"] = True
                restart_playback_monitor()
                
        except Exception as ex:
            print(f"DEBUG: jump failed: {ex}")

    home_view.on_word_click = handle_word_jump
    
    async def playback_monitor_loop(expected_run_id):
        """Monitor playback progress and update highlighting"""
        last_word_idx = -1
        
        while True:
            try:
                if expected_run_id != playback_monitor_state["run_id"]:
                    break

                # Check if we should exit the loop
                if not current_audio_state["is_playing"] and not current_audio_state["is_paused"]:
                    break
                
                # If paused, just wait
                if current_audio_state["is_paused"]:
                    await asyncio.sleep(0.1)
                    continue
                
                # Check if playback finished (not busy and not paused)
                if not pygame.mixer.music.get_busy() and not current_audio_state["is_paused"]:
                    # Playback finished
                    current_audio_state["is_playing"] = False
                    home_view.btn_play_pause.selected = False
                    home_view.text_input.read_only = False
                    home_view.hide_highlighted_text()  # Hide highlighting when done
                    home_view.set_status("播放完成", ft.Icons.CHECK_CIRCLE_OUTLINE, ft.Colors.GREEN_100)
                    sync_home_controls(home_view.btn_play_pause, home_view.text_input)
                    break
                
                # Get current position in ms
                # FIX: Add Start Offset because get_pos() returns time since play() started
                rel_ms = pygame.mixer.music.get_pos()
                if rel_ms == -1: rel_ms = 0
                pos_ms = current_audio_state.get("current_playback_start_ms", 0) + rel_ms
                
                # Check for Sentence Stop Condition
                stop_at = current_audio_state.get("stop_playback_at_ms")
                if stop_at and pos_ms >= stop_at:
                    # Pause playback as if user clicked pause
                    pygame.mixer.music.pause()
                    current_audio_state["is_paused"] = True
                    current_audio_state["stop_playback_at_ms"] = None # Clear constraint so Resume works
                    home_view.btn_play_pause.selected = False
                    home_view.set_status("已暂停 (句末)", ft.Icons.PAUSE_CIRCLE_OUTLINE, ft.Colors.AMBER_100)
                    sync_home_controls(home_view.btn_play_pause)
                    continue
                
                timestamps = current_audio_state.get("timestamps")
                if timestamps:
                    # Update current word index for highlighting
                    if timestamps.get("words"):
                        for i, word in enumerate(timestamps["words"]):
                            if word["start_ms"] <= pos_ms < word["end_ms"]:
                                if i != last_word_idx:
                                    current_audio_state["current_word_index"] = i
                                    home_view.update_highlight_position(i)
                                    last_word_idx = i
                                break
                    
                    # Update current sentence index
                    if timestamps.get("sentences"):
                        for i, sent in enumerate(timestamps["sentences"]):
                            if sent["start_ms"] <= pos_ms < sent["end_ms"]:
                                current_audio_state["current_sentence_index"] = i
                                break
                
            except Exception as ex:
                print(f"DEBUG: Playback monitor error: {ex}")
            
            await asyncio.sleep(0.05)  # 50ms update interval

    # Bindings
    def bind_async(handler):
        def _wrapped(e):
            async def _runner():
                result = handler(e)
                if inspect.isawaitable(result):
                    await result
            page.run_task(_runner)
        return _wrapped

    home_view.btn_gen_a.on_click = bind_async(handle_generate_a)
    home_view.btn_gen_b.on_click = bind_async(handle_generate_b)
    home_view.btn_stop.on_click = handle_stop_audio
    home_view.btn_replay.on_click = handle_replay
    home_view.btn_play_pause.on_click = bind_async(handle_pause_resume)
    home_view.btn_prev_sentence.on_click = bind_async(handle_prev_sentence)
    home_view.btn_next_sentence.on_click = bind_async(handle_next_sentence)
    
    # Voice Selection Handler
    # Voice Selection Handler
    def handle_voice_selected(e):
        payload = e.control.data if isinstance(e.control.data, dict) else {"name": e.control.data, "side": "right"}
        new_voice = payload.get("name")
        voice_side = payload.get("side") or "right"
        key = "selected_voice_left" if voice_side == "left" else "selected_voice_right"
        current_voice = settings_manager.get(key)

        if not new_voice:
            return
        if new_voice == current_voice:
            print(f"Selected same voice on {voice_side}, no change.")
            return

        settings_manager.set(key, new_voice)
        settings_manager.save_settings()
        
        print(f"Voice Slot Updated: {voice_side}='{new_voice}'")

        home_view.set_selections(
            get_voice_for_slot("left"),
            get_voice_for_slot("right")
        )
        page.update()

    home_view.on_voice_selected = handle_voice_selected

    # Pin Toggle Handler (Always on Top) with persistence
    def handle_pin_toggle(is_pinned):
        print(f"DEBUG: Pin Toggle Requested -> {is_pinned}")
        
        # Use new Flet API
        page.window.always_on_top = is_pinned
        
        # Save state to settings
        settings_manager.set("pin_enabled", is_pinned)
        settings_manager.save_settings()
        
        page.update()
        print(f"DEBUG: Pin Status Now -> {page.window.always_on_top}")
    
    home_view.on_pin_toggle = handle_pin_toggle
    
    # Restore pin state from settings
    saved_pin = settings_manager.get("pin_enabled", False)
    if saved_pin:
        page.window.always_on_top = True
        home_view.btn_pin.selected = True
        page.update()

    # History Handlers
    def handle_history_play(record):
        if not record:
            return
        path = record.get("path")
        if not path or not os.path.exists(path):
            show_message("历史音频不存在，已移除该记录", True)
            history_manager.remove_record(record)
            history_view.populate_history(history_manager.get_records())
            return
        home_view.set_input_text(record.get("text", ""), mark_as_generated=True)
        handle_play_audio({
            "path": path,
            "text": record.get("text"),
        })

    def handle_history_delete(record):
        if not record:
            return
        # Unload audio to release file lock (Windows specific)
        if record and record.get("path") == current_audio_state.get("path"):
            handle_stop_audio(None)
            current_audio_state["path"] = None
            current_audio_state["timestamps"] = None
            current_audio_state["text"] = None
        try:
             pygame.mixer.music.unload() 
        except Exception:
             pygame.mixer.music.stop()
             
        history_manager.remove_record(record)
        history_view.populate_history(history_manager.get_records())
        show_message("历史记录已删除")

    def handle_history_clear():
        print("DEBUG: handle_history_clear TRIGGERED")
        try:
             # Stop playback first
             handle_stop_audio(None)
             current_audio_state["path"] = None
             current_audio_state["timestamps"] = None
             current_audio_state["text"] = None
             try: pygame.mixer.music.unload()
             except Exception: pass
             try: pygame.mixer.music.stop()
             except Exception: pass
             
             history_manager.clear_records() # Deletes files and clears list
             print("DEBUG: Manager cleared.")
             
             # Force UI Refresh
             new_records = history_manager.get_records()
             print(f"DEBUG: Repopulating with {len(new_records)} records")
             history_view.populate_history(new_records)
             page.update()
             show_message("历史记录已清空")
             
        except Exception as ex:
             print(f"ERROR in handle_history_clear: {ex}")
             show_message(f"清空历史失败: {ex}", True)

    history_view.on_play_audio = handle_history_play
    history_view.on_delete_item = handle_history_delete
    history_view.on_clear_all = handle_history_clear

    def handle_selection_text(text, source="selection"):
        if not text:
            return

        async def _runner():
            home_view.set_input_text(text)

        page.run_task(_runner)

    def handle_monitored_text(text, source="clipboard"):
        if not text:
            return
        async def _runner():
            home_view.set_input_text(text)
            now = time.monotonic()
            if text == clipboard_generation_state["text"] and now - clipboard_generation_state["at"] < 1.2:
                print("DEBUG: duplicate clipboard generation ignored")
                return
            clipboard_generation_state["text"] = text
            clipboard_generation_state["at"] = now
            voice = get_voice_for_slot("right")
            await generate_audio_for_voice(text, voice, status_message="正在根据复制内容生成音频...")

        page.run_task(_runner)

    monitor_manager = MonitorManager(
        on_clipboard_change=handle_monitored_text,
        on_selection_captured=handle_selection_text,
        on_selection_trigger=lambda pos: threading.Thread(
            target=monitor_manager.simulate_copy,
            args=(pos,),
            daemon=True,
        ).start()
    )
    monitor_manager.start_monitors() 

    # Tray Logic
    def on_tray_show_hide():
        if page.window.visible:
            page.window.visible = False
            page.update()
            return
        page.run_task(restore_main_window)
        
    def on_tray_exit():
        page.run_task(destroy_main_window)

    def ensure_tray_manager():
        nonlocal tray_manager
        if tray_manager is None:
            tray_manager = TrayIconManager(on_show_hide=on_tray_show_hide, on_exit=on_tray_exit)
        return tray_manager

    def sync_tray_icon():
        if settings_manager.get("minimize_to_tray", False):
            ensure_tray_manager().start()
        elif tray_manager:
            tray_manager.stop()

    sync_tray_icon()



    # Window Events
    page.window.prevent_close = True # Handle close manually

    def window_event(e):
        if e.data == "close":
            if settings_manager.get("minimize_to_tray", False):
                print("DEBUG: Window Close -> Hiding to Tray")
                page.window.visible = False
                page.update()
            else:
                on_tray_exit()
        elif e.data == "minimize":
             if settings_manager.get("minimize_to_tray", False):
                 print("DEBUG: Window Minimized -> Hiding to Tray")
                 page.window.visible = False
                 page.update()
             else:
                 print("DEBUG: Window Minimized -> Taskbar (Normal)")
                 pass

    page.window.on_event = window_event
    
    # Settings Handler
    def handle_save_settings(settings_dict):
        print("DEBUG: Saving Settings:", settings_dict)
        for k, v in settings_dict.items():
            settings_manager.set(k, v)
        settings_manager.save_settings()

        if "appearance_mode" in settings_dict:
            page.theme_mode = (
                ft.ThemeMode.DARK
                if settings_dict["appearance_mode"] == "dark"
                else ft.ThemeMode.LIGHT
            )
            refresh_navigation_styles()
        
        # Apply immediate effects checks
        monitor_manager.start_monitors() # Will adjust/stop based on new flags
        sync_tray_icon()
        
        # Update dual mode
        is_dual = settings_manager.get("dual_voice_mode_enabled", False)
        home_view.set_dual_mode(is_dual)

        if "tts_engine" in settings_dict:
            if settings_manager.get("tts_engine") == "local_kokoro" and not settings_manager.get("local_engine_ready", False):
                show_message("离线引擎未安装或未校验，请在设置页点击“自动下载并安装”或“重新校验”。", True)

        refresh_local_engine_status_ui()
        
        page.update()

    settings_view.on_save_settings = handle_save_settings

    page.update()

    # Load Initial History
    history_view.populate_history(history_manager.get_records())
    
    # Init Views state
    is_dual = settings_manager.get("dual_voice_mode_enabled", False)
    home_view.set_dual_mode(is_dual)
    home_view.set_selections(
        get_voice_for_slot("left"),
        get_voice_for_slot("right")
    )
    settings_view.set_values(settings_manager.settings)
    refresh_local_engine_status_ui()
    
    page.update()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    ft.app(target=main)
