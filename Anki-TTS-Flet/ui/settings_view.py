import flet as ft
from utils.i18n import i18n
from config.constants import APP_VERSION, GITHUB_URL, DATA_DIR
from config.ui_scale import (
    DEFAULT_UI_SCALE_PERCENT,
    MAX_UI_SCALE_PERCENT,
    MIN_UI_SCALE_PERCENT,
    UiScale,
    normalize_ui_scale_percent,
)
import webbrowser
import os
from types import SimpleNamespace


def create_dropdown(**kwargs):
    on_event = kwargs.pop("on_event", None)
    # Flet 0.28.3's new Dropdown has no height constraint and keeps a 48 px
    # field at every UI scale. The pinned M2 control accepts scaled height.
    try:
        return ft.DropdownM2(on_change=on_event, **kwargs)
    except TypeError:
        return ft.DropdownM2(on_select=on_event, **kwargs)


class SettingsView(ft.Container):
    def __init__(self, page: ft.Page, ui_scale: UiScale | None = None):
        super().__init__()
        self._host_page = page
        self.ui_scale = ui_scale or UiScale()
        px = self.ui_scale.px
        font = self.ui_scale.font
        switch_scale = ft.Scale(scale=self.ui_scale.factor, alignment=ft.alignment.top_left)
        button_style = ft.ButtonStyle(
            padding=ft.padding.symmetric(horizontal=px(16), vertical=px(8)),
            text_style=ft.TextStyle(size=font(14)),
            icon_size=px(18),
        )

        self._switch_label_texts = {}

        def switch_slot(control):
            label = ft.Text(
                control.label,
                size=font(14),
                on_tap=lambda _, switch=control: self._toggle_switch_from_label(switch),
            )
            self._switch_label_texts[id(control)] = label
            control.label = None
            # Positioned children keep native geometry while the stack reserves scaled space.
            control.left = 0
            control.top = 0
            control.width = 60
            control.height = 48
            return ft.Row(
                [
                    ft.Stack([control], width=px(60), height=px(48), clip_behavior=ft.ClipBehavior.NONE),
                    label,
                ],
                spacing=px(8),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        self.expand = True
        self.padding = px(20)
        
        # Header
        self.header = ft.Text(i18n.get("tab_settings"), size=font(24), weight="bold")
        
        # Components
        # 1. Appearance
        self.theme_switch = ft.Switch(
            label=i18n.get("theme_label", "Dark Mode"),
            scale=switch_scale,
            value=False,
            on_change=self._on_theme_changed
        )
        
        self.language_dropdown = create_dropdown(
            value=i18n.current_language,
            options=[
                ft.dropdownm2.Option("zh", "中文"),
                ft.dropdownm2.Option("en", "English"),
            ],
            width=px(120),
            height=px(56),
            text_size=font(14),
            content_padding=px(12),
            select_icon_size=px(24),
            dense=True,
            on_event=self._on_language_change,
        )

        self.ui_scale_input = ft.TextField(
            value=str(DEFAULT_UI_SCALE_PERCENT),
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.NumbersOnlyInputFilter(),
            hint_text=f"{MIN_UI_SCALE_PERCENT}-{MAX_UI_SCALE_PERCENT}",
            suffix_text="%",
            width=px(120),
            height=px(56),
            text_size=font(14),
            content_padding=px(12),
            on_change=self._on_ui_scale_input_changed,
            on_blur=self._on_ui_scale_changed,
            on_submit=self._on_ui_scale_changed,
        )
        self._ui_scale_draft = str(DEFAULT_UI_SCALE_PERCENT)
        
        # 2. Behavior
        self.autoplay_switch = ft.Switch(
            label=i18n.get("settings_autoplay_label"),
            scale=switch_scale,
            value=True,
            on_change=self._save_settings
        )

        # 2.1 TTS Engine (Online / Offline)
        self.tts_engine_dropdown = create_dropdown(
            value="edge_online",
            options=[
                ft.dropdownm2.Option("edge_online", i18n.get("tts_engine_edge_online")),
                ft.dropdownm2.Option("local_kokoro", i18n.get("tts_engine_local_kokoro")),
            ],
            width=px(280),
            height=px(56),
            text_size=font(14),
            content_padding=px(12),
            select_icon_size=px(24),
            dense=True,
            on_event=self._on_tts_engine_change,
        )

        self.local_engine_status_value = ft.Text(
            i18n.get("local_engine_status_not_ready"),
            size=font(12),
            color=ft.Colors.OUTLINE,
            selectable=True,
        )
        self.local_engine_path_text = ft.Text("", size=font(12), color=ft.Colors.OUTLINE, selectable=True)

        self.local_engine_busy_ring = ft.ProgressRing(width=px(16), height=px(16), visible=False)

        self.local_engine_auto_fallback_switch = ft.Switch(
            label=i18n.get("local_engine_auto_fallback_label"),
            scale=switch_scale,
            value=True,
            on_change=self._save_settings,
        )

        self.local_engine_source_dropdown = create_dropdown(
            value="official",
            options=[
                ft.dropdownm2.Option("official", i18n.get("local_engine_download_source_official")),
                ft.dropdownm2.Option("mirror", i18n.get("local_engine_download_source_mirror")),
            ],
            width=px(140),
            height=px(56),
            text_size=font(14),
            content_padding=px(12),
            select_icon_size=px(24),
            dense=True,
            on_event=self._save_settings,
        )

        self.local_engine_install_button = ft.OutlinedButton(
            text=i18n.get("local_engine_install_button"),
            icon=ft.Icons.DOWNLOAD,
            height=px(40),
            style=button_style,
            on_click=self._on_local_engine_install,
        )
        self.local_engine_healthcheck_button = ft.OutlinedButton(
            text=i18n.get("local_engine_healthcheck_button"),
            icon=ft.Icons.VERIFIED,
            height=px(40),
            style=button_style,
            on_click=self._on_local_engine_healthcheck,
        )
        self.local_engine_manual_button = ft.OutlinedButton(
            text=i18n.get("local_engine_manual_button"),
            icon=ft.Icons.TERMINAL,
            height=px(40),
            style=button_style,
            on_click=self._on_local_engine_manual,
        )
        self.local_engine_open_dir_button = ft.OutlinedButton(
            text=i18n.get("local_engine_open_dir_button"),
            icon=ft.Icons.FOLDER_OPEN,
            height=px(40),
            style=button_style,
            on_click=self._on_local_engine_open_dir,
        )
        self.local_engine_uninstall_button = ft.OutlinedButton(
            text=i18n.get("local_engine_uninstall_button"),
            icon=ft.Icons.DELETE,
            height=px(40),
            style=ft.ButtonStyle(
                color=ft.Colors.RED_400,
                padding=ft.padding.symmetric(horizontal=px(16), vertical=px(8)),
                text_style=ft.TextStyle(size=font(14)),
                icon_size=px(18),
            ),
            on_click=self._on_local_engine_uninstall,
        )

        self.ctrl_c_switch = ft.Switch(
            label=i18n.get("settings_enable_clipboard_monitor_label", i18n.get("settings_enable_ctrl_c_label")),
            scale=switch_scale,
            value=True,
            on_change=self._save_settings
        )

        self.selection_switch = ft.Switch(
            label=i18n.get("settings_enable_selection_label"),
            scale=switch_scale,
            value=False,
            on_change=self._on_selection_mode_change
        )
        
        self.dual_voice_mode_switch = ft.Switch(
            label=i18n.get("settings_dual_voice_mode_label"),
            scale=switch_scale,
            value=False,
            on_change=self._on_dual_voice_mode_change
        )

        self.selection_dual_mode_switch = ft.Switch(
            label=i18n.get("settings_selection_dual_mode_label"),
            scale=switch_scale,
            value=False,
            on_change=self._on_selection_dual_mode_change
        )

        self.copy_file_switch = ft.Switch(
            label=i18n.get("copy_audio_to_clipboard"), 
            scale=switch_scale,
            value=True,
            on_change=self._save_settings
        )

        self.tray_switch = ft.Switch(
             label=i18n.get("settings_minimize_to_tray_label", "Minimize to Tray"),
             scale=switch_scale,
             value=False,
             on_change=self._save_settings
        )
        
        # Window Size Controls
        self.window_width_input = ft.TextField(
            label="",
            hint_text="750",
            value="750",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=px(100),
            height=px(56),
            text_size=font(14),
            content_padding=px(12),
            on_blur=self._on_window_size_changed
        )
        
        self.window_height_input = ft.TextField(
            label="",
            hint_text="850",
            value="850",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=px(100),
            height=px(56),
            text_size=font(14),
            content_padding=px(12),
            on_blur=self._on_window_size_changed
        )
        
        self.reset_size_button = ft.OutlinedButton(
            text=i18n.get("reset_button"),
            icon=ft.Icons.RESTORE,
            height=px(40),
            style=button_style,
            on_click=self._reset_window_size
        )
        
        self.max_files_input = ft.TextField(
            label=i18n.get("settings_max_files_label"),
            value="20",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=px(200),
            height=px(56),
            text_size=font(14),
            content_padding=px(12),
            on_blur=self._save_settings
        )
        
        self.open_data_dir_button = ft.OutlinedButton(
            text=i18n.get("open_data_dir", "Open Data Directory"),
            icon=ft.Icons.FOLDER_OPEN,
            height=px(40),
            style=button_style,
            on_click=lambda _: os.startfile(DATA_DIR) if os.name == 'nt' else None
        )
        
        # Section headers as instance variables for dynamic language update
        self.section_appearance_text = ft.Text(i18n.get("section_appearance"), weight="bold", size=font(16))
        self.language_label_text = ft.Text(i18n.get("language_label"), size=font(14))
        self.ui_scale_label_text = ft.Text(i18n.get("ui_scale_label"), size=font(14))
        self.section_playback_text = ft.Text(i18n.get("section_playback"), weight="bold", size=font(16))
        self.section_tts_engine_text = ft.Text(i18n.get("section_tts_engine"), weight="bold", size=font(16))
        self.tts_engine_label_text = ft.Text(i18n.get("tts_engine_label"), size=font(14))
        self.local_engine_status_label_text = ft.Text(i18n.get("local_engine_status_label"), size=font(14), color="grey")
        self.local_engine_source_label_text = ft.Text(i18n.get("local_engine_download_source_label"), size=font(14))
        self.section_voice_mode_text = ft.Text(i18n.get("section_voice_mode"), weight="bold", size=font(16))
        self.section_selection_mode_text = ft.Text(i18n.get("section_selection_mode"), weight="bold", size=font(16))
        self.section_copy_mode_text = ft.Text(i18n.get("section_copy_mode"), weight="bold", size=font(16))
        self.section_window_text = ft.Text(i18n.get("section_window"), weight="bold", size=font(16))
        self.window_size_label_text = ft.Text(i18n.get("window_size_label"), size=font(14), color="grey")
        self.section_storage_text = ft.Text(i18n.get("section_storage"), weight="bold", size=font(16))
        self.section_maintenance_text = ft.Text(i18n.get("section_maintenance"), weight="bold", size=font(16))
        self.check_updates_button = ft.OutlinedButton(
            text=i18n.get("check_for_updates"),
            icon=ft.Icons.OPEN_IN_NEW,
            height=px(40),
            style=button_style,
            on_click=lambda _: webbrowser.open(GITHUB_URL)
        )
        self.version_text = ft.Text(f"Version {APP_VERSION}", size=font(12), color="grey", text_align=ft.TextAlign.CENTER)

        # Dialogs
        self.local_engine_manual_text = ft.TextField(
            value="",
            read_only=True,
            multiline=True,
            min_lines=12,
            text_size=font(14),
            content_padding=px(12),
        )
        self.local_engine_manual_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(i18n.get("local_engine_manual_title"), size=font(20)),
            content=ft.Column(
                [
                    ft.Text(i18n.get("local_engine_manual_hint"), size=font(12), color=ft.Colors.OUTLINE),
                    self.local_engine_manual_text,
                ],
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=px(10),
            ),
            actions=[
                ft.TextButton(text=i18n.get("local_engine_manual_close", i18n.get("dialog_cancel")), height=px(40), style=button_style, on_click=self._close_manual_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.local_engine_uninstall_confirm = ft.AlertDialog(
            modal=True,
            title=ft.Text(i18n.get("local_engine_uninstall_confirm_title", "Confirm Uninstall"), size=font(20)),
            content=ft.Text(i18n.get("local_engine_uninstall_confirm_msg", "Uninstall offline engine?"), size=font(14)),
            actions=[
                ft.TextButton(text=i18n.get("dialog_cancel", "Cancel"), height=px(40), style=button_style, on_click=self._close_uninstall_dialog),
                ft.TextButton(text=i18n.get("dialog_confirm", "Confirm"), height=px(40), style=button_style, on_click=self._confirm_uninstall),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.content = ft.Column(
            [
                self.header,
                ft.Divider(),
                
                self.section_appearance_text,
                switch_slot(self.theme_switch),
                ft.Row([
                    self.language_label_text,
                    self.language_dropdown
                ], spacing=px(10), wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([
                    self.ui_scale_label_text,
                    self.ui_scale_input
                ], spacing=px(10), wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=px(10), color="transparent"),
                
                self.section_playback_text,
                switch_slot(self.autoplay_switch),
                ft.Divider(height=px(10), color="transparent"),

                self.section_tts_engine_text,
                ft.Row(
                    [self.tts_engine_label_text, self.tts_engine_dropdown],
                    spacing=px(10),
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [self.local_engine_status_label_text, self.local_engine_status_value, self.local_engine_busy_ring],
                    spacing=px(10),
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.local_engine_path_text,
                switch_slot(self.local_engine_auto_fallback_switch),
                ft.Row(
                    [self.local_engine_source_label_text, self.local_engine_source_dropdown],
                    spacing=px(10),
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [self.local_engine_install_button, self.local_engine_healthcheck_button],
                    spacing=px(10),
                    wrap=True,
                ),
                ft.Row(
                    [self.local_engine_manual_button, self.local_engine_open_dir_button],
                    spacing=px(10),
                    wrap=True,
                ),
                self.local_engine_uninstall_button,
                ft.Divider(height=px(10), color="transparent"),

                self.section_voice_mode_text,
                switch_slot(self.dual_voice_mode_switch),
                ft.Divider(height=px(10), color="transparent"),

                self.section_selection_mode_text,
                switch_slot(self.selection_switch),
                switch_slot(self.selection_dual_mode_switch),
                ft.Divider(height=px(10), color="transparent"),

                self.section_copy_mode_text,
                switch_slot(self.ctrl_c_switch),
                switch_slot(self.copy_file_switch),
                ft.Divider(height=px(10), color="transparent"),
                
                self.section_window_text,
                switch_slot(self.tray_switch),
                self.window_size_label_text,
                ft.Row(
                    [
                        self.window_width_input,
                        ft.Text("×", size=font(20)),
                        self.window_height_input,
                        self.reset_size_button
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=px(10),
                    wrap=True,
                ),
                ft.Divider(height=px(10), color="transparent"),
                
                self.section_storage_text,
                ft.Row([
                    self.max_files_input,
                    self.open_data_dir_button
                ], spacing=px(10), wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                
                ft.Divider(),
                self.section_maintenance_text,
                self.check_updates_button,
                self.version_text
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=px(10),
        )

    def _is_mounted(self):
        return getattr(self, "page", None) is not None

    def _safe_update(self, *controls):
        if not self._is_mounted():
            return
        try:
            if controls:
                for control in controls:
                    control.update()
                return
            self.update()
        except Exception as ex:
            print(f"DEBUG: SettingsView safe update skipped: {ex}")

    def _on_theme_changed(self, e):
        self._host_page.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        self._save_settings(e)
        self._host_page.update()
    
    def _on_language_change(self, e):
        """Apply language change immediately and persist it."""
        new_lang = e.control.value
        print(f"DEBUG: _on_language_change triggered with: {new_lang}")
        
        i18n.set_language(new_lang)
        print(f"DEBUG: i18n language set to: {i18n.current_language}")
        
        # Save to settings
        if hasattr(self, 'on_save_settings'):
            self.on_save_settings({
                "language": new_lang
            })
            print("DEBUG: Settings saved")

        self.refresh_texts()
        if hasattr(self, "on_language_changed") and self.on_language_changed:
            self.on_language_changed(new_lang)
        self._host_page.update()

    def _open_dialog(self, dialog):
        if hasattr(self._host_page, "open"):
            self._host_page.open(dialog)
            return
        self._host_page.dialog = dialog
        dialog.open = True
        self._host_page.update()

    def _close_host_dialog(self, dialog):
        if hasattr(self._host_page, "close"):
            self._host_page.close(dialog)
            return
        dialog.open = False
        self._host_page.update()
        if getattr(self._host_page, "dialog", None) is dialog:
            self._host_page.dialog = None

    def set_local_engine_busy(self, busy: bool, status_message: str | None = None):
        self.local_engine_busy_ring.visible = bool(busy)
        for btn in [
            self.local_engine_install_button,
            self.local_engine_healthcheck_button,
            self.local_engine_manual_button,
            self.local_engine_open_dir_button,
            self.local_engine_uninstall_button,
        ]:
            btn.disabled = bool(busy)
        if status_message is not None:
            self.local_engine_status_value.value = status_message
        self._safe_update(
            self.local_engine_busy_ring,
            self.local_engine_install_button,
            self.local_engine_healthcheck_button,
            self.local_engine_manual_button,
            self.local_engine_open_dir_button,
            self.local_engine_uninstall_button,
            self.local_engine_status_value,
        )

    def update_local_engine_status(self, settings_dict, base_dir: str = ""):
        ready = bool((settings_dict or {}).get("local_engine_ready", False))
        last_error = str((settings_dict or {}).get("local_engine_last_error", "") or "")
        if ready:
            self.local_engine_status_value.value = i18n.get("local_engine_status_ready")
            self.local_engine_status_value.color = ft.Colors.GREEN_600
        elif last_error:
            self.local_engine_status_value.value = i18n.get("local_engine_status_error", error=last_error)
            self.local_engine_status_value.color = ft.Colors.RED_400
        else:
            self.local_engine_status_value.value = i18n.get("local_engine_status_not_ready")
            self.local_engine_status_value.color = ft.Colors.OUTLINE

        self.local_engine_path_text.value = base_dir or ""
        self._safe_update(self.local_engine_status_value, self.local_engine_path_text)

    def _on_tts_engine_change(self, e):
        self._save_settings(e)

    def _on_local_engine_install(self, e):
        if hasattr(self, "on_local_engine_install") and self.on_local_engine_install:
            self.on_local_engine_install()

    def _on_local_engine_healthcheck(self, e):
        if hasattr(self, "on_local_engine_healthcheck") and self.on_local_engine_healthcheck:
            self.on_local_engine_healthcheck()

    def _on_local_engine_uninstall(self, e):
        self._open_dialog(self.local_engine_uninstall_confirm)

    def _close_uninstall_dialog(self, e):
        self._close_host_dialog(self.local_engine_uninstall_confirm)

    def _confirm_uninstall(self, e):
        self._close_uninstall_dialog(e)
        if hasattr(self, "on_local_engine_uninstall") and self.on_local_engine_uninstall:
            self.on_local_engine_uninstall()

    def _on_local_engine_manual(self, e):
        instructions = {}
        if hasattr(self, "on_local_engine_manual_instructions") and self.on_local_engine_manual_instructions:
            try:
                instructions = self.on_local_engine_manual_instructions() or {}
            except Exception as ex:
                instructions = {"error": str(ex)}

        self.local_engine_manual_text.value = self._format_manual_instructions(instructions)
        self._safe_update(self.local_engine_manual_text)
        self._open_dialog(self.local_engine_manual_dialog)

    def _format_manual_instructions(self, instructions: dict) -> str:
        if not isinstance(instructions, dict):
            return str(instructions)
        if instructions.get("error"):
            return f"ERROR: {instructions.get('error')}"

        lines: list[str] = []
        downloads_dir = instructions.get("downloads_dir") or ""
        if downloads_dir:
            lines.append("Target directory:")
            lines.append(str(downloads_dir))
            lines.append("")

        runtime = instructions.get("runtime") or {}
        model = instructions.get("model") or {}

        if isinstance(runtime, dict):
            lines.append("Runtime:")
            lines.append(f"- file: {runtime.get('asset_name')}")
            lines.append(f"- url:  {runtime.get('url')}")
            lines.append(f"- checksum.txt: {runtime.get('checksum_url')}")
            lines.append("")

        if isinstance(model, dict):
            lines.append("Model:")
            lines.append(f"- file: {model.get('asset_name')}")
            lines.append(f"- url:  {model.get('url')}")
            lines.append(f"- checksum.txt: {model.get('checksum_url')}")
            lines.append("")

        ps = instructions.get("powershell") or []
        if isinstance(ps, list) and ps:
            lines.append("PowerShell:")
            lines.extend([str(x) for x in ps if str(x).strip()])

        return "\n".join(lines).strip()

    def _close_manual_dialog(self, e):
        self._close_host_dialog(self.local_engine_manual_dialog)

    def _on_local_engine_open_dir(self, e):
        if hasattr(self, "on_local_engine_open_dir") and self.on_local_engine_open_dir:
            self.on_local_engine_open_dir()

    def _on_dual_voice_mode_change(self, e):
        if not e.control.value:
            self.selection_dual_mode_switch.value = False
        self._safe_update(self.selection_dual_mode_switch)
        self._save_settings(e)

    def _on_selection_mode_change(self, e):
        if not e.control.value and self.selection_dual_mode_switch.value:
            self.selection_dual_mode_switch.value = False
            self._safe_update(self.selection_dual_mode_switch)
        self._save_settings(e)

    def _on_selection_dual_mode_change(self, e):
        if e.control.value:
            if not self.selection_switch.value:
                self.selection_switch.value = True
            if not self.dual_voice_mode_switch.value:
                self.dual_voice_mode_switch.value = True
            self._safe_update(self.selection_switch, self.dual_voice_mode_switch)
        self._save_settings(e)

    def _on_ui_scale_input_changed(self, e):
        self._ui_scale_draft = str(
            getattr(e, "data", None) or getattr(e.control, "value", "")
        )

    def _on_ui_scale_changed(self, e):
        normalized = normalize_ui_scale_percent(self._ui_scale_draft)
        self._ui_scale_draft = str(normalized)
        self.ui_scale_input.value = self._ui_scale_draft
        self._safe_update(self.ui_scale_input)
        self._save_settings(e)

    def _save_settings(self, e):
        if hasattr(self, 'on_save_settings'):
            selection_dual_enabled = bool(self.selection_dual_mode_switch.value)
            selection_enabled = bool(self.selection_switch.value or selection_dual_enabled)
            dual_voice_enabled = bool(self.dual_voice_mode_switch.value or selection_dual_enabled)
            # Collect current values
            settings = {
                "tts_engine": self.tts_engine_dropdown.value,
                "local_engine_auto_fallback": self.local_engine_auto_fallback_switch.value,
                "local_engine_download_source": self.local_engine_source_dropdown.value,
                "max_audio_files": self.max_files_input.value,
                "autoplay_enabled": self.autoplay_switch.value,
                "dual_voice_mode_enabled": dual_voice_enabled,
                "selection_dual_mode_enabled": selection_dual_enabled,
                "monitor_clipboard_enabled": self.ctrl_c_switch.value,
                "monitor_selection_enabled": selection_enabled,
                "copy_path_enabled": self.copy_file_switch.value,
                "minimize_to_tray": self.tray_switch.value,
                "appearance_mode": "dark" if self.theme_switch.value else "light",
                "ui_scale_percent": normalize_ui_scale_percent(self.ui_scale_input.value),
            }
            self.on_save_settings(settings)

    def set_values(self, settings_dict):
        self.max_files_input.value = str(settings_dict.get("max_audio_files", 20))
        self.autoplay_switch.value = settings_dict.get("autoplay_enabled", True)

        self.tts_engine_dropdown.value = settings_dict.get("tts_engine", "edge_online") or "edge_online"
        self.local_engine_auto_fallback_switch.value = settings_dict.get("local_engine_auto_fallback", True)
        self.local_engine_source_dropdown.value = settings_dict.get("local_engine_download_source", "official") or "official"
        
        selection_dual_enabled = settings_dict.get("selection_dual_mode_enabled", False)
        selection_enabled = settings_dict.get("monitor_selection_enabled", False) or selection_dual_enabled
        dual_voice_enabled = settings_dict.get("dual_voice_mode_enabled", False) or selection_dual_enabled

        self.selection_switch.value = selection_enabled
        self.dual_voice_mode_switch.value = dual_voice_enabled
        self.selection_dual_mode_switch.value = selection_dual_enabled
        
        self.ctrl_c_switch.value = settings_dict.get("monitor_clipboard_enabled", False)
        
        self.copy_file_switch.value = settings_dict.get("copy_path_enabled", True)
        self.tray_switch.value = settings_dict.get("minimize_to_tray", False)
        self.theme_switch.value = settings_dict.get("appearance_mode", "light") == "dark"

        ui_scale_percent = normalize_ui_scale_percent(
            settings_dict.get("ui_scale_percent", DEFAULT_UI_SCALE_PERCENT)
        )
        self._ui_scale_draft = str(ui_scale_percent)
        self.ui_scale_input.value = self._ui_scale_draft
        
        # Window size
        self.window_width_input.value = str(settings_dict.get("window_width", 750))
        self.window_height_input.value = str(settings_dict.get("window_height", 850))
        self.update_local_engine_status(settings_dict, base_dir=str(settings_dict.get("local_engine_base_dir") or ""))
        if self._is_mounted():
            self.update()

    def update_window_size_display(self, width, height):
        """Called from main.py when window is resized to sync the UI"""
        self.window_width_input.value = str(int(width))
        self.window_height_input.value = str(int(height))
        self._safe_update(self.window_width_input, self.window_height_input)

    def _on_window_size_changed(self, e):
        """When user changes the size input fields"""
        try:
            new_width = int(self.window_width_input.value)
            new_height = int(self.window_height_input.value)
            
            # Validate minimum size
            new_width = max(400, new_width)
            new_height = max(500, new_height)
            
            if hasattr(self, 'on_window_size_change'):
                self.on_window_size_change(new_width, new_height)
        except ValueError:
            pass  # Ignore invalid input

    def _reset_window_size(self, e):
        """Reset to default 750x850"""
        self.window_width_input.value = "750"
        self.window_height_input.value = "850"
        self._safe_update(self.window_width_input, self.window_height_input)
        
        if hasattr(self, 'on_window_size_change'):
            self.on_window_size_change(750, 850)

    def _set_switch_label(self, control, value):
        self._switch_label_texts[id(control)].value = value

    def _toggle_switch_from_label(self, control):
        if control.disabled:
            return
        control.value = not control.value
        if control.on_change:
            control.on_change(SimpleNamespace(control=control))
        self._safe_update(control)

    def refresh_texts(self):
        self.header.value = i18n.get("tab_settings")
        self._set_switch_label(self.theme_switch, i18n.get("theme_label", "Dark Mode"))
        self._set_switch_label(self.autoplay_switch, i18n.get("settings_autoplay_label"))
        self.section_tts_engine_text.value = i18n.get("section_tts_engine")
        self.tts_engine_label_text.value = i18n.get("tts_engine_label")
        self.local_engine_status_label_text.value = i18n.get("local_engine_status_label")
        self.local_engine_source_label_text.value = i18n.get("local_engine_download_source_label")

        self.tts_engine_dropdown.options = [
            ft.dropdownm2.Option("edge_online", i18n.get("tts_engine_edge_online")),
            ft.dropdownm2.Option("local_kokoro", i18n.get("tts_engine_local_kokoro")),
        ]
        self._set_switch_label(self.local_engine_auto_fallback_switch, i18n.get("local_engine_auto_fallback_label"))
        self.local_engine_source_dropdown.options = [
            ft.dropdownm2.Option("official", i18n.get("local_engine_download_source_official")),
            ft.dropdownm2.Option("mirror", i18n.get("local_engine_download_source_mirror")),
        ]
        self.local_engine_install_button.text = i18n.get("local_engine_install_button")
        self.local_engine_healthcheck_button.text = i18n.get("local_engine_healthcheck_button")
        self.local_engine_manual_button.text = i18n.get("local_engine_manual_button")
        self.local_engine_open_dir_button.text = i18n.get("local_engine_open_dir_button")
        self.local_engine_uninstall_button.text = i18n.get("local_engine_uninstall_button")
        self.local_engine_manual_dialog.title.value = i18n.get("local_engine_manual_title")
        self.local_engine_manual_dialog.content.controls[0].value = i18n.get("local_engine_manual_hint")
        self.local_engine_manual_dialog.actions[0].text = i18n.get("local_engine_manual_close", i18n.get("dialog_cancel"))

        self.local_engine_uninstall_confirm.title.value = i18n.get("local_engine_uninstall_confirm_title")
        self.local_engine_uninstall_confirm.content.value = i18n.get("local_engine_uninstall_confirm_msg")
        self.local_engine_uninstall_confirm.actions[0].text = i18n.get("dialog_cancel", "Cancel")
        self.local_engine_uninstall_confirm.actions[1].text = i18n.get("dialog_confirm", "Confirm")

        self._set_switch_label(self.ctrl_c_switch, i18n.get("settings_enable_clipboard_monitor_label", i18n.get("settings_enable_ctrl_c_label")))
        self._set_switch_label(self.selection_switch, i18n.get("settings_enable_selection_label"))
        self._set_switch_label(self.dual_voice_mode_switch, i18n.get("settings_dual_voice_mode_label"))
        self._set_switch_label(self.selection_dual_mode_switch, i18n.get("settings_selection_dual_mode_label"))
        self._set_switch_label(self.copy_file_switch, i18n.get("copy_audio_to_clipboard"))
        self._set_switch_label(self.tray_switch, i18n.get("settings_minimize_to_tray_label", "Minimize to Tray"))
        self.max_files_input.label = i18n.get("settings_max_files_label")
        self.reset_size_button.text = i18n.get("reset_button")
        self.open_data_dir_button.text = i18n.get("open_data_dir", "Open Data Directory")
        self.check_updates_button.text = i18n.get("check_for_updates")
        self.version_text.value = f"Version {APP_VERSION}"
        self.section_appearance_text.value = i18n.get("section_appearance")
        self.language_label_text.value = i18n.get("language_label")
        self.ui_scale_label_text.value = i18n.get("ui_scale_label")
        self.section_playback_text.value = i18n.get("section_playback")
        self.section_voice_mode_text.value = i18n.get("section_voice_mode")
        self.section_selection_mode_text.value = i18n.get("section_selection_mode")
        self.section_copy_mode_text.value = i18n.get("section_copy_mode")
        self.section_window_text.value = i18n.get("section_window")
        self.window_size_label_text.value = i18n.get("window_size_label")
        self.section_storage_text.value = i18n.get("section_storage")
        self.section_maintenance_text.value = i18n.get("section_maintenance")
        self._safe_update()
