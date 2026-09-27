import flet as ft
from datetime import datetime
from utils.i18n import i18n
from core.voices import get_display_voice_name
from config.ui_scale import UiScale

class HistoryView(ft.Container):
    def __init__(self, page: ft.Page, ui_scale: UiScale | None = None):
        super().__init__()
        self._host_page = page
        self.ui_scale = ui_scale or UiScale()
        px = self.ui_scale.px
        font = self.ui_scale.font
        self.expand = True
        self.padding = px(20)

        self.header_text = ft.Text(i18n.get("history_panel_title"), size=font(24), weight="bold")
        self.clear_all_button = ft.TextButton(
            text=i18n.get("history_clear_all"),
            icon=ft.Icons.DELETE_SWEEP,
            style=ft.ButtonStyle(
                color=ft.Colors.RED_400,
                text_style=ft.TextStyle(size=font(14)),
                icon_size=px(18),
                padding=ft.padding.symmetric(horizontal=px(12), vertical=px(8)),
            ),
            on_click=self._on_clear_all
        )
        
        # Header
        self.header = ft.Row(
            [
                self.header_text,
                self.clear_all_button,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )
        
        # Dialog
        self.confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(i18n.get("history_clear_confirm_title", "Confirm Clear"), size=font(20)),
            content=ft.Text(i18n.get("history_clear_confirm_msg", "Delete all history?"), size=font(14)),
            actions=[
                ft.TextButton(
                    text=i18n.get("dialog_cancel", "Cancel"),
                    style=ft.ButtonStyle(text_style=ft.TextStyle(size=font(14))),
                    on_click=self._close_dialog,
                ),
                ft.TextButton(
                    text=i18n.get("dialog_confirm", "Yes"),
                    style=ft.ButtonStyle(text_style=ft.TextStyle(size=font(14))),
                    on_click=self._confirm_clear,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            title_padding=ft.padding.only(left=px(24), top=px(24), right=px(24)),
            content_padding=ft.padding.symmetric(horizontal=px(24), vertical=px(16)),
            actions_padding=px(8),
        )

        # List
        self.history_list = ft.ListView(expand=True, spacing=px(10))
        
        self.content = ft.Column(
            expand=True,
            alignment=ft.MainAxisAlignment.START,
            controls=[
                self.header,
                ft.Divider(height=px(16)),
                self.history_list
            ]
        )

    def _is_mounted(self):
        return getattr(self, "page", None) is not None

    def _safe_update(self):
        if self._is_mounted():
            try:
                self.update()
            except Exception as ex:
                print(f"DEBUG: HistoryView safe update skipped: {ex}")
        
    def populate_history(self, records):
        self.history_list.controls.clear()
        
        if not records:
            self.history_list.controls.append(ft.Text(i18n.get("history_empty"), italic=True, size=self.ui_scale.font(14)))
            self._safe_update()
            return

        for rec in records:
            # Create dismissible (swipe to delete) or just list tile with action
            # Flet's Dismissible is great for mobile, but for desktop explicit button is better.
            
            text_preview = rec.get("text", "")
            if len(text_preview) > 50: text_preview = text_preview[:50] + "..."
            
            voice_text = get_display_voice_name(rec.get("voice") or rec.get("voice_key"))
            timestamp_text = self._format_timestamp(rec.get("timestamp") or rec.get("time"))
            meta_parts = [part for part in [voice_text, timestamp_text] if part]
            meta_text = " | ".join(meta_parts) if meta_parts else "-"

            action_buttons = ft.Row(
                [
                    ft.TextButton(
                        text=i18n.get("control_play_pause", "播放"),
                        icon=ft.Icons.PLAY_ARROW,
                        style=ft.ButtonStyle(
                            text_style=ft.TextStyle(size=self.ui_scale.font(14)),
                            icon_size=self.ui_scale.px(18),
                            padding=ft.padding.symmetric(horizontal=self.ui_scale.px(12), vertical=self.ui_scale.px(8)),
                        ),
                        on_click=lambda e, r=rec: self._play_audio(r),
                    ),
                    ft.TextButton(
                        text=i18n.get("history_rec_delete", "删除"),
                        icon=ft.Icons.DELETE,
                        style=ft.ButtonStyle(
                            color=ft.Colors.RED_400,
                            text_style=ft.TextStyle(size=self.ui_scale.font(14)),
                            icon_size=self.ui_scale.px(18),
                            padding=ft.padding.symmetric(horizontal=self.ui_scale.px(12), vertical=self.ui_scale.px(8)),
                        ),
                        on_click=lambda e, r=rec: self._delete_item(r),
                    ),
                ],
                spacing=0,
                tight=True,
            )

            tile = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.AUDIO_FILE, color=ft.Colors.INDIGO, size=self.ui_scale.px(24)),
                        ft.Column(
                            [
                                ft.Text(text_preview, weight="bold", size=self.ui_scale.font(14)),
                                ft.Text(meta_text, size=self.ui_scale.font(12), color=ft.Colors.OUTLINE),
                            ],
                            expand=True,
                            spacing=self.ui_scale.px(2)
                        ),
                        action_buttons,
                    ],
                ),
                padding=self.ui_scale.px(10),
                bgcolor="surfaceVariant",
                border_radius=self.ui_scale.px(10),
            )
            self.history_list.controls.append(tile)
            
        self._safe_update()

    def _play_audio(self, record):
        print(f"DEBUG: History play clicked -> {record.get('path') if isinstance(record, dict) else record}")
        if hasattr(self, 'on_play_audio'):
            self.on_play_audio(record)

    def _delete_item(self, record):
        print(f"DEBUG: History delete clicked -> {record.get('path') if isinstance(record, dict) else record}")
        if hasattr(self, 'on_delete_item'):
            self.on_delete_item(record)

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

    def _on_clear_all(self, e):
        print("DEBUG: Opening Clear All Dialog")
        self._open_dialog(self.confirm_dialog)

    def _close_dialog(self, e):
        self._close_host_dialog(self.confirm_dialog)

    def _confirm_clear(self, e):
        print("DEBUG: User confirmed Clear All")
        self._close_dialog(e)
        if hasattr(self, 'on_clear_all'):
            print("DEBUG: Calling on_clear_all callback")
            self.on_clear_all()
        else:
            print("ERROR: No on_clear_all callback bound")

    def _on_item_click(self, record):
        if hasattr(self, 'on_click_record'):
            self.on_click_record(record)

    def refresh_texts(self):
        self.header_text.value = i18n.get("history_panel_title")
        self.clear_all_button.text = i18n.get("history_clear_all")
        self.confirm_dialog.title.value = i18n.get("history_clear_confirm_title", "Confirm Clear")
        self.confirm_dialog.content.value = i18n.get("history_clear_confirm_msg", "Delete all history?")
        self.confirm_dialog.actions[0].text = i18n.get("dialog_cancel", "Cancel")
        self.confirm_dialog.actions[1].text = i18n.get("dialog_confirm", "Yes")
        self._safe_update()

    def _format_timestamp(self, value):
        if not value:
            return ""

        try:
            return datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError, OSError):
            return str(value)
