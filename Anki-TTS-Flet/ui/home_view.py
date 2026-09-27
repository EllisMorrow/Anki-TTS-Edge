import flet as ft
from utils.i18n import i18n
from core.kokoro_voice_catalog import KOKORO_MULTI_LANG_V1_1_DOC_URL
from config.ui_scale import UiScale

MAX_HIGHLIGHT_WORDS = 320


def create_dropdown(**kwargs):
    on_event = kwargs.pop("on_event", None)
    # Flet 0.28.3's new Dropdown has no height constraint and keeps a 48 px
    # field at every UI scale. The pinned M2 control accepts scaled height.
    try:
        return ft.DropdownM2(on_change=on_event, **kwargs)
    except TypeError:
        return ft.DropdownM2(on_select=on_event, **kwargs)

class HomeView(ft.Container):
    def __init__(self, page: ft.Page, ui_scale: UiScale | None = None):
        super().__init__()
        self._host_page = page
        self.ui_scale = ui_scale or UiScale()
        px = self.ui_scale.px
        font = self.ui_scale.font
        self.expand = True
        self.padding = px(20)
        
        # --- UI Components ---
        
        # 0. Status Bar (shown at top of text input area)
        self.status_bar = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.INFO_OUTLINE, size=px(14)),
                ft.Text("", size=font(12)),
            ], spacing=px(5)),
            visible=False,
            bgcolor="primaryContainer",
            border_radius=px(5),
            padding=ft.padding.symmetric(horizontal=px(10), vertical=px(3)),
            margin=ft.margin.only(bottom=px(5)),
        )
        
        # 1. Text Input with edit detection
        self._last_generated_text = ""  # Track last generated text to detect edits
        self.text_input = ft.TextField(
            hint_text="",
            multiline=True,
            min_lines=3,
            max_lines=5,
            text_size=font(14),
            content_padding=px(12),
            cursor_width=px(2),
            expand=True, # Expand to fill Stack
            border_color=ft.Colors.OUTLINE,
            focused_border_color="primary",
            on_change=self._on_text_input_change,
        )
        
        # 1.5 Highlighted Text Overlay (same size as text_input, shown during playback)
        self._word_timings = []  # Store word timings for highlighting
        self._current_word_index = -1
        self._status_text = ""
        self.highlighted_text_column = ft.Column(
            controls=[],
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
        )
        # Fixed height to match text_input min_lines=3 (approximately 72px for 3 lines)
        # Fixed height to match text_input min_lines=3 (approximately 72px for 3 lines)
        self.highlighted_text_overlay = ft.Container(
            content=self.highlighted_text_column,
            visible=False,
            bgcolor="surface",
            border=ft.border.all(1, ft.Colors.TRANSPARENT), # Invisible border to match input
            # Use margin/padding to match TextField's internal content area
            # TextField has internal padding (~12px). 
            padding=px(12),
            expand=True, # Expand to fill Stack
            clip_behavior=ft.ClipBehavior.HARD_EDGE,  # Clip overflow content
            alignment=ft.alignment.Alignment(-1, -1),
            # CRITICAL FIX: Ensure it has a minimum height to prevent stack collapse
            height=None, # Let it expand, but...
        )
        
        # 2. Parameters (Sliders)
        self.rate_slider = self._build_slider(i18n.get("rate_label"), 0, -100, 100)
        self.volume_slider = self._build_slider(i18n.get("volume_label"), 0, -100, 100)
        self.input_label_text = ft.Text(i18n.get("input_text_label"), weight="bold", size=font(16))
        self.rate_label_text = ft.Text(i18n.get("rate_label"), size=font(14))
        self.volume_label_text = ft.Text(i18n.get("volume_label"), size=font(14))

        # 2.5 Filters (Dual Dropdowns)
        self.lang_dropdown_left = create_dropdown(
            label="Language (Left)",
            text_size=font(14),
            label_style=ft.TextStyle(size=font(12)),
            content_padding=px(12),
            select_icon_size=px(24),
            height=px(56),
            on_event=lambda e: self._on_filter_change('left'),
            expand=True,
            dense=True
        )
        self.lang_dropdown_right = create_dropdown(
            label="Language (Right)", 
            text_size=font(14),
            label_style=ft.TextStyle(size=font(12)),
            content_padding=px(12),
            select_icon_size=px(24),
            height=px(56),
            on_event=lambda e: self._on_filter_change('right'),
            expand=True,
            dense=True
        )

        # 2.6 Offline (Local) Voice Selection (speaker id / sid)
        self._tts_engine_id = "edge_online"
        self._local_sid_left = 0
        self._local_sid_right = 0
        # In single-voice mode (dual_mode=False), which slot is considered "active" for generation.
        self._single_active_slot = "right"
        self.offline_hint_text = ft.Text(i18n.get("offline_voice_hint"), size=font(12))
        self.offline_hint_container = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=px(14)),
                    self.offline_hint_text,
                ],
                spacing=px(6),
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            visible=False,
            bgcolor="primaryContainer",
            border_radius=px(8),
            padding=ft.padding.symmetric(horizontal=px(10), vertical=px(6)),
        )

        self.offline_demo_button = ft.TextButton(
            text=i18n.get("offline_voice_demo_link", "离线语音音效听"),
            icon=ft.Icons.OPEN_IN_NEW,
            style=ft.ButtonStyle(
                padding=ft.padding.all(0),
                text_style=ft.TextStyle(size=font(14)),
                icon_size=px(18),
            ),
            on_click=self._open_offline_demo,
        )
        self.offline_demo_container = ft.Container(
            content=ft.Row([self.offline_demo_button], spacing=px(6)),
            visible=False,
            padding=ft.padding.only(left=px(2)),
        )
        
        # 3. Voice Lists (Dual Column)
        # Using ListView for efficient scrolling
        self._voice_row_extent = px(54)
        self._voice_list_padding = px(10)
        self._voice_edge_padding = {"left": self._voice_list_padding, "right": self._voice_list_padding}
        self._voice_scroll_offsets = {"left": 0.0, "right": 0.0}
        self._voice_viewport_heights = {"left": None, "right": None}
        self._voice_focus_pending = {"left": False, "right": False}
        self._selected_voice_indices = {"left": None, "right": None}
        self._voice_selection_initialized = False
        self._favorite_keys = set()
        self._favorite_buttons = {}
        self.list_left = ft.ListView(
            expand=True, item_extent=self._voice_row_extent,
            padding=self._voice_list_padding, auto_scroll=False,
            build_controls_on_demand=False,
            on_scroll_interval=0,
            on_scroll=lambda e: self._remember_voice_scroll("left", e),
        )
        self.list_right = ft.ListView(
            expand=True, item_extent=self._voice_row_extent,
            padding=self._voice_list_padding, auto_scroll=False,
            build_controls_on_demand=False,
            on_scroll_interval=0,
            on_scroll=lambda e: self._remember_voice_scroll("right", e),
        )
        
        # Region navigation (auto-wrap instead of scroll)
        self.region_nav_left = ft.Row(
            spacing=px(5),
            wrap=True,
            run_spacing=px(5),
        )
        self.region_nav_right = ft.Row(
            spacing=px(5),
            wrap=True,
            run_spacing=px(5),
        )
        
        # Headers for lists
        self.header_left = ft.Text(i18n.get("voice_list_label_1"), weight="bold", size=font(14))
        self.header_right = ft.Text(i18n.get("voice_list_label_2"), weight="bold", size=font(14))
        
        # Containers for lists (border style like text input, no gray background)
        list_container_left = ft.Container(
            content=ft.Column([
                self.header_left,
                ft.Container(content=self.region_nav_left, padding=ft.padding.only(bottom=px(5))),
                self.list_left
            ], spacing=px(5)),
            expand=True,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=px(10),
            padding=px(10),
        )
        
        list_container_right = ft.Container(
            content=ft.Column([
                self.header_right,
                ft.Container(content=self.region_nav_right, padding=ft.padding.only(bottom=px(5))),
                self.list_right
            ], spacing=px(5)),
            expand=True,
            border=ft.border.all(1, ft.Colors.OUTLINE),
            border_radius=px(10),
            padding=px(10),
        )
        
        # 4. Action Buttons
        self.btn_gen_a = ft.FilledTonalButton(
            text=i18n.get("generate_button_previous"),
            icon=ft.Icons.PLAY_CIRCLE_OUTLINE, 
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=px(8)),
                text_style=ft.TextStyle(size=font(14)),
                icon_size=px(18),
                padding=ft.padding.symmetric(horizontal=px(16), vertical=px(8)),
            ),
            expand=True,
            height=px(50),
        )
        self.btn_gen_b = ft.FilledButton(
            text=i18n.get("generate_button_latest"),
            icon=ft.Icons.PLAY_CIRCLE_FILLED, 
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=px(8)),
                text_style=ft.TextStyle(size=font(14)),
                icon_size=px(18),
                padding=ft.padding.symmetric(horizontal=px(16), vertical=px(8)),
            ),
            expand=True, 
            height=px(50),
        )

        # 4.5 Audio Control Buttons (Replay, Play/Pause, Stop)
        self.btn_replay = ft.IconButton(
            icon=ft.Icons.REPLAY,
            tooltip=i18n.get("control_replay", "重播"),
            icon_size=px(20),
            width=px(40), height=px(40), padding=px(8),
        )
        self.btn_play_pause = ft.IconButton(
            icon=ft.Icons.PLAY_CIRCLE_OUTLINE,
            selected_icon=ft.Icons.PAUSE_CIRCLE_OUTLINE,
            tooltip=i18n.get("control_play_pause", "播放/暂停"),
            icon_size=px(20),
            width=px(40), height=px(40), padding=px(8),
        )
        self.btn_stop = ft.IconButton(
            icon=ft.Icons.STOP_CIRCLE_OUTLINED,
            tooltip=i18n.get("control_stop", "停止"),
            icon_color=ft.Colors.RED,
            icon_size=px(20),
            width=px(40), height=px(40), padding=px(8),
        )
        
        # 4.6 Sentence Navigation Buttons
        self.btn_prev_sentence = ft.IconButton(
            icon=ft.Icons.SKIP_PREVIOUS,
            tooltip=i18n.get("control_prev_sentence", "上一句"),
            icon_size=px(20),
            width=px(40), height=px(40), padding=px(8),
        )
        self.btn_next_sentence = ft.IconButton(
            icon=ft.Icons.SKIP_NEXT,
            tooltip=i18n.get("control_next_sentence", "下一句"),
            icon_size=px(20),
            width=px(40), height=px(40), padding=px(8),
        )
        
        # 5. Pin Button
        self.btn_pin = ft.IconButton(
             icon=ft.Icons.PUSH_PIN_OUTLINED,
             selected_icon=ft.Icons.PUSH_PIN,
             tooltip=i18n.get("window_pin", "置顶窗口"),
             icon_size=px(20),
             width=px(40), height=px(40), padding=px(8),
             on_click=self._toggle_pin
        )
        
        # 6. Expand/Collapse Button for text input
        self._text_expanded = False
        self.btn_expand_collapse = ft.IconButton(
            icon=ft.Icons.EXPAND_MORE,
            tooltip=i18n.get("expand_text_input", "展开"),
            icon_size=px(16),
            width=px(24), height=px(24), padding=px(4),
            on_click=self._toggle_expand_collapse,
        )

        # --- Layout Assembly ---
        # Playback controls row (small buttons)
        playback_controls = ft.Row(
            [
                self.btn_replay,
                self.btn_play_pause,
                self.btn_stop,
                ft.VerticalDivider(width=px(5)),
                self.btn_prev_sentence,
                self.btn_next_sentence,
            ],
            spacing=0,
        )
        
        # Header Row - with text label and playback controls next to it
        header_row = ft.Row(
            [
                self.input_label_text,
                ft.Container(width=px(10)), # Spacer
                playback_controls,
                ft.Container(expand=True), # Spacer to push pin to right
                self.btn_pin
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        
        # Expand/Collapse button container (centered at bottom of text input)
        # We put it in a separate container below the stack, but with negative margin to overlap border?
        # Simpler: Just put it in the column below. 
        expand_button_container = ft.Container(
            content=self.btn_expand_collapse,
            alignment=ft.alignment.Alignment(0, 0),
            height=px(20),
        )
        
        # Text input container with Stack overlay for highlighting
        self.text_input_stack = ft.Stack([
            self.text_input,
            self.highlighted_text_overlay,  # Overlay for word highlighting
        ])
        
        # Wrap Stack in a Container to enforce minimum height stability
        # Using fixed height to match max_lines=5 (approx 140px)
        # We will manually toggle this height in _toggle_expand_collapse
        self.text_input_wrapper = ft.Container(
            content=self.text_input_stack,
            height=px(140),
        )
        
        self.text_input_container = ft.Container(
            content=ft.Column(
                [
                    self.status_bar,  # Status bar at top
                    self.text_input_wrapper, # Use the wrapper instead of direct stack
                    expand_button_container,
                ],
                spacing=0,
            ),
        )
        
        # Parameters row (will be hidden when text is expanded)
        self.params_row = ft.Container(
            theme=ft.Theme(slider_theme=ft.SliderTheme(
                track_height=px(4),
                thumb_size=ft.Size(px(20), px(20)),
                value_indicator_text_style=ft.TextStyle(size=font(14)),
                year_2023=False,
            )) if self.ui_scale.factor != 1 else None,
            content=ft.Row(
                [
                    ft.Column([self.rate_label_text, self.rate_slider], expand=True),
                    ft.Column([self.volume_label_text, self.volume_slider], expand=True),
                ],
                spacing=px(20)
            ),
            visible=True,
            animate_opacity=300,
        )
        
        # Store references for expand/collapse
        self.list_container_left = list_container_left
        self.list_container_right = list_container_right

        # Filters row (online only)
        self.filters_row = ft.Row([self.lang_dropdown_left, self.lang_dropdown_right], spacing=px(20))

        # Voice selection areas (online + offline)
        self.voice_row_online = ft.Row(
            [list_container_left, list_container_right],
            expand=True,
            spacing=px(20),
        )
        self.voice_area = ft.Column(
            [
                self.offline_hint_container,
                self.offline_demo_container,
                self.voice_row_online,
            ],
            spacing=px(10),
            expand=True,
        )
        
        self.content = ft.Column(
            expand=True,
            alignment=ft.MainAxisAlignment.START,
            controls=[
                header_row,
                self.text_input_container,
                ft.Divider(height=px(10), color="transparent"),
                
                # Filters
                self.filters_row,
                ft.Divider(height=px(10), color="transparent"),

                # Voice Selection Area
                self.voice_area,
                
                ft.Divider(height=px(10), color="transparent"),
                
                # Parameters Row
                self.params_row,
                
                ft.Divider(height=px(10), color="transparent"),
                
                # Buttons Row (only generate buttons, playback controls moved to header)
                ft.Row(
                    [
                        self.btn_gen_a, 
                        self.btn_gen_b,
                    ],
                    spacing=px(10),
                )
            ],
        )

    def set_compact_height_layout(self, enabled: bool):
        """Keep all home-page actions reachable in short windows."""
        if hasattr(self, "_voice_viewport_heights"):
            self._voice_viewport_heights = {"left": None, "right": None}
        enabled = bool(enabled)
        if getattr(self, "_compact_height_layout", None) == enabled:
            return
        self._compact_height_layout = enabled

        if enabled:
            self.content.scroll = ft.ScrollMode.AUTO
            self.voice_area.expand = False
            self.voice_area.height = self.ui_scale.px(190)
        else:
            self.content.scroll = None
            self.voice_area.expand = True
            self.voice_area.height = None

        self._safe_update(self.voice_area)

    def _toggle_expand_collapse(self, e):
        """Toggle text input expansion to cover parameters area
        
        动态高度实现：展开时隐藏中间区域（Filters和Voice Selection），
        让text_input_wrapper使用expand=True填充可用空间到params_row顶部
        """
        self._text_expanded = not self._text_expanded
        
        # 获取主内容Column的controls引用
        main_content = self.content
        
        if self._text_expanded:
            # 展开：隐藏中间区域，让文本框扩展填充
            self.text_input.max_lines = 30  # 允许更多行
            self.text_input.min_lines = 15
            
            # 隐藏Filters和Voice Selection（索引2-5的控件）
            # 索引: 0=header_row, 1=text_input_container, 2=Divider, 3=Filters, 4=Divider, 5=VoiceSelection, 6=Divider, 7=params_row, 8=Divider, 9=Buttons
            for i in [2, 3, 4, 5, 6]:  # 隐藏Divider, Filters, Divider, VoiceSelection, Divider
                if i < len(main_content.controls):
                    main_content.controls[i].visible = False
            
            # 让text_input_wrapper扩展填充空间
            self.text_input_wrapper.expand = True
            self.text_input_wrapper.height = None  # 移除固定高度
            self.text_input_container.expand = True  # 容器也需要扩展
            
            self.btn_expand_collapse.icon = ft.Icons.EXPAND_LESS
            self.btn_expand_collapse.tooltip = i18n.get("collapse_text_input", "收纳")
        else:
            # 收缩：恢复中间区域显示
            self.text_input.max_lines = 5
            self.text_input.min_lines = 3
            
            # 恢复显示Filters和Voice Selection
            for i in [2, 3, 4, 5, 6]:
                if i < len(main_content.controls):
                    main_content.controls[i].visible = True
            
            # 恢复固定高度
            self.text_input_wrapper.expand = False
            self.text_input_wrapper.height = self.ui_scale.px(140)
            self.text_input_container.expand = False
            
            self.btn_expand_collapse.icon = ft.Icons.EXPAND_MORE
            self.btn_expand_collapse.tooltip = i18n.get("expand_text_input", "展开")
        
        # 关键修复：如果正在播放（覆盖层可见），同步更新覆盖层并重新应用高亮
        if self.highlighted_text_overlay.visible:
            if self._text_expanded:
                # 展开时覆盖层也使用expand
                self.highlighted_text_overlay.expand = True
                self.highlighted_text_overlay.height = None
                self.highlighted_text_column.expand = True
                self.highlighted_text_column.height = None
            else:
                # 收缩时恢复固定高度
                self.highlighted_text_overlay.expand = False
                self.highlighted_text_overlay.height = self.ui_scale.px(140)
                self.highlighted_text_column.expand = False
                overlay_content_height = self.ui_scale.px(140 - 24)
                self.highlighted_text_column.height = overlay_content_height
            
            # 强制重新应用当前高亮状态，避免展开后高亮丢失
            current_idx = self._current_word_index
            if current_idx >= 0 and hasattr(self, '_word_containers') and self._word_containers:
                HIGHLIGHT_COLOR = ft.Colors.AMBER_200
                for i, container in enumerate(self._word_containers):
                    if i == current_idx:
                        container.bgcolor = HIGHLIGHT_COLOR
                    else:
                        container.bgcolor = None
            
            self.highlighted_text_column.update()
            self.highlighted_text_overlay.update()
        
        # 同步更新Stack的expand属性
        self.text_input_stack.expand = self._text_expanded
        
        self.text_input.update()
        self.text_input_stack.update()
        self.text_input_wrapper.update()
        self.text_input_container.update()
        self.btn_expand_collapse.update()
        main_content.update()
        self.update()

    def _build_slider(self, label, value, min_v, max_v):
        return ft.Slider(
            min=min_v, 
            max=max_v, 
            divisions=200, 
            value=value, 
            label="{value}%",
            active_color="primary",
        )

    # --- Methods to Populate Data (To be called by Controller) ---
    def set_tts_engine(self, engine_id: str):
        engine_id = (engine_id or "edge_online").strip() or "edge_online"
        if engine_id != self._tts_engine_id:
            self._voice_scroll_offsets = {"left": 0.0, "right": 0.0}
            self._voice_viewport_heights = {"left": None, "right": None}
        self._tts_engine_id = engine_id
        is_offline = engine_id == "local_kokoro"

        self.filters_row.visible = not is_offline
        self.offline_hint_container.visible = is_offline
        self.offline_demo_container.visible = is_offline
        self._safe_update(self.filters_row, self.offline_hint_container, self.offline_demo_container, self.voice_area)

    def set_local_voice_sids(self, left_sid: int, right_sid: int):
        try:
            self._local_sid_left = int(left_sid) if left_sid is not None else 0
        except Exception:
            self._local_sid_left = 0
        try:
            self._local_sid_right = int(right_sid) if right_sid is not None else 0
        except Exception:
            self._local_sid_right = 0

        # Refresh selection badges when offline voices are shown.
        if self._tts_engine_id == "local_kokoro" and hasattr(self, "all_voices_data"):
            self._render_voices(self.all_voices_data, side="both")

    def set_dual_mode(self, enabled):
        self.dual_mode = enabled
        if enabled:
            self.btn_gen_a.visible = True
            # Dual mode: show both explicit buttons.
            self.btn_gen_b.text = i18n.get("generate_button_latest")
        else:
            self.btn_gen_a.visible = False
            # Single mode: make the button label explicit about which slot is active.
            self.btn_gen_b.text = (
                i18n.get("generate_button_previous")
                if getattr(self, "_single_active_slot", "right") == "left"
                else i18n.get("generate_button_latest")
            )
        self._safe_update(self.btn_gen_a, self.btn_gen_b)

    def set_single_active_slot(self, slot: str):
        raw = str(slot or "right").strip().lower()
        self._single_active_slot = "left" if raw == "left" else "right"
        if getattr(self, "dual_mode", False):
            return
        self.btn_gen_b.text = (
            i18n.get("generate_button_previous")
            if self._single_active_slot == "left"
            else i18n.get("generate_button_latest")
        )
        self._safe_update(self.btn_gen_b)

    def set_selections(self, left, right):
        first_selection = not self._voice_selection_initialized
        self._voice_selection_initialized = True
        self.selected_voice_left = left
        self.selected_voice_right = right
        if hasattr(self, 'all_voices_data'):
            # Refresh both sides
            self._render_voices(self.all_voices_data, locate_selected=first_selection)

    @staticmethod
    def _favorite_key(item):
        if item.get("sid") is not None:
            try:
                return f"local_kokoro:v1_1:{int(item['sid'])}"
            except (TypeError, ValueError):
                return None
        name = item.get("name")
        return f"edge_online:{name}" if name else None

    def set_favorites(self, keys):
        """Set the shared favorite keys used by both voice lists."""
        self._favorite_keys = set(keys or ())
        self._refresh_favorite_buttons()

    def _refresh_favorite_buttons(self, keys=None):
        for key in keys if keys is not None else self._favorite_buttons:
            favorite = key in self._favorite_keys
            for button, hovered, _side in self._favorite_buttons.get(key, ()):
                button.icon = ft.Icons.STAR if favorite else ft.Icons.STAR_BORDER
                button.tooltip = i18n.get("voice_favorite_remove") if favorite else i18n.get("voice_favorite_add")
                button.visible = favorite or hovered[0]
                self._safe_update(button)

    def _on_favorite_clicked(self, key):
        if key in self._favorite_keys:
            self._favorite_keys.remove(key)
        else:
            self._favorite_keys.add(key)
        self._refresh_favorite_buttons((key,))
        callback = getattr(self, "on_favorite_toggled", None)
        if callback is not None:
            callback(key, key in self._favorite_keys)

    def _remember_voice_scroll(self, side, event):
        if event.pixels is not None:
            self._voice_scroll_offsets[side] = max(0.0, event.pixels)
        viewport_height = getattr(event, "viewport_dimension", None)
        if viewport_height is not None and viewport_height > 0:
            self._voice_viewport_heights[side] = viewport_height
            if self._voice_focus_pending[side]:
                self._voice_focus_pending[side] = False
                self._scroll_selected_voice_to_center(side)

    def focus_selected_voices(self, side="both"):
        """Center each selected voice after the voice page has been mounted."""
        if not self._is_mounted():
            return
        sides = ("left", "right") if side == "both" else (side,)
        for list_side in sides:
            if self._selected_voice_indices[list_side] is None:
                continue
            if self._voice_viewport_heights[list_side] is None:
                # A one-pixel scroll yields the actual ListView viewport after layout.
                # If the list cannot scroll, its selected voice is already visible.
                self._voice_focus_pending[list_side] = True
                self._voice_list(list_side).scroll_to(offset=1, duration=0)
            else:
                self._scroll_selected_voice_to_center(list_side)

    def _voice_list(self, side):
        return self.list_left if side == "left" else self.list_right

    def _scroll_selected_voice_to_center(self, side):
        index = self._selected_voice_indices[side]
        viewport_height = self._voice_viewport_heights[side]
        if index is None or not viewport_height:
            return
        list_view = self._voice_list(side)
        # Leave enough space to center even the first and last item.
        edge_padding = max(self._voice_list_padding, (viewport_height - self._voice_row_extent) / 2)
        self._set_voice_edge_padding(side, edge_padding)
        content_height = len(list_view.controls) * self._voice_row_extent + 2 * edge_padding
        max_offset = max(0, content_height - viewport_height)
        center_offset = (
            edge_padding + index * self._voice_row_extent
            - (viewport_height - self._voice_row_extent) / 2
        )
        list_view.scroll_to(offset=max(0, min(center_offset, max_offset)), duration=0)

    def _set_voice_edge_padding(self, side, edge_padding):
        if self._voice_edge_padding[side] == edge_padding:
            return
        self._voice_edge_padding[side] = edge_padding
        list_view = self._voice_list(side)
        list_view.padding = ft.padding.only(
            left=self._voice_list_padding, right=self._voice_list_padding,
            top=edge_padding, bottom=edge_padding,
        )
        self._safe_update(list_view)

    def populate_voices(self, voice_list, side='both', locate_selected=True):
        # voice_list is a list of dicts: {"name": str, "lang": str, "region": str}
        self.all_voices_data = voice_list # Store for filtering
        
        # Extract Languages for Dropdowns
        langs = sorted(list(set([v["lang"] for v in voice_list])))
        
        # Create DISTINCT option lists for each dropdown to avoid shared control ownership issues
        options_left = [ft.dropdownm2.Option(l) for l in langs]
        options_right = [ft.dropdownm2.Option(l) for l in langs]
        
        # Update Dropdowns (preserve selection if possible)
        current_l = self.lang_dropdown_left.value
        current_r = self.lang_dropdown_right.value
        
        self.lang_dropdown_left.options = options_left
        self.lang_dropdown_right.options = options_right
        
        # Set Defaults if empty
        if not current_l:
            # Try find zh-CN or starts with zh
            zh = next((l for l in langs if l.startswith("zh")), langs[0] if langs else None)
            self.lang_dropdown_left.value = zh
            
        if not current_r:
             # Try find en-US or starts with en
            en = next((l for l in langs if l.startswith("en")), langs[0] if langs else None)
            self.lang_dropdown_right.value = en

        self._render_voices(voice_list, side, locate_selected=locate_selected)

    def _on_filter_change(self, side):
        if hasattr(self, 'all_voices_data'):
            self._render_voices(self.all_voices_data, side, locate_selected=True)

    def _render_voices(self, voice_list, side='both', locate_selected=False):
        # Rebuilding controls can emit an on_scroll event at zero before restoration.
        saved_offsets = self._voice_scroll_offsets.copy()
        
        def filter_list(full_list, lang_filter):
            if not lang_filter: return full_list
            return [v for v in full_list if v["lang"] == lang_filter]

        # Offline Kokoro voices should be selectable on BOTH lists, independent of the language filters.
        if getattr(self, "_tts_engine_id", "edge_online") == "local_kokoro":
            left_voices = voice_list
            right_voices = voice_list
        else:
            left_voices = filter_list(voice_list, self.lang_dropdown_left.value)
            right_voices = filter_list(voice_list, self.lang_dropdown_right.value)
        
        def create_tiles(target_list, nav_row, data_source, list_ref, region_positions, list_side):
            target_list.controls.clear()
            nav_row.controls.clear()
            region_positions.clear()
            selected_index = None
            
            if not data_source:
                return selected_index
            
            # Collect unique regions for navigation
            regions = []
            for item in data_source:
                if item["region"] not in regions:
                    regions.append(item["region"])
            
            # Create region navigation chips
            for region in regions:
                chip = ft.Container(
                    content=ft.Text(region, size=self.ui_scale.font(11), weight="w500", color="onPrimaryContainer"),
                    padding=ft.padding.symmetric(
                        horizontal=self.ui_scale.px(10),
                        vertical=self.ui_scale.px(4),
                    ),
                    bgcolor="primaryContainer",
                    border_radius=self.ui_scale.px(12),
                    on_click=lambda e, r=region, lv=list_ref, rp=region_positions: self._scroll_to_region_by_index(lv, rp.get(r, 0)),
                    ink=True,
                )
                nav_row.controls.append(chip)
            
            current_region = None
            
            for item in data_source:
                name = item["name"]
                region = item["region"]
                
                # Region section header
                if region != current_region:
                    # Record position before adding the header
                    region_positions[region] = len(target_list.controls)
                    
                    # Simple elegant header - centered badge style
                    section_header = ft.Container(
                        key=f"region_{region}",
                        height=self._voice_row_extent,
                        alignment=ft.alignment.Alignment(0, 0),
                        content=ft.Container(
                            content=ft.Text(
                                region,
                                weight="bold",
                                size=self.ui_scale.font(12),
                                color="onSecondaryContainer",
                                text_align=ft.TextAlign.CENTER,
                                no_wrap=True,
                            ),
                            bgcolor="secondaryContainer",
                            padding=ft.padding.symmetric(horizontal=self.ui_scale.px(12), vertical=self.ui_scale.px(4)),
                            border_radius=self.ui_scale.px(15),
                        ),
                    )
                    target_list.controls.append(section_header)
                    current_region = region
                
                # Simple display name extraction
                display_name = item.get("display_name") or name

                # Selection status
                is_dual = bool(getattr(self, "dual_mode", False))
                active_slot = getattr(self, "_single_active_slot", "right")
                sid = item.get("sid") if isinstance(item, dict) else None
                sid_int = None
                if sid is not None:
                    try:
                        sid_int = int(sid)
                    except Exception:
                        sid_int = None
                    is_right = sid_int is not None and sid_int == getattr(self, "_local_sid_right", None)
                    is_left = sid_int is not None and sid_int == getattr(self, "_local_sid_left", None)
                else:
                    is_right = hasattr(self, "selected_voice_right") and name == self.selected_voice_right
                    is_left = hasattr(self, "selected_voice_left") and name == self.selected_voice_left
                
                trailing_content = None
                bg = "surfaceVariant"
                
                # Colors
                BG_B = "primaryContainer"  # Teal-tinted in both modes
                BG_A = ft.Colors.INDIGO_50 if self._host_page.theme_mode == ft.ThemeMode.LIGHT else ft.Colors.INDIGO_900
                BG_BOTH = ft.Colors.BLUE_50 if self._host_page.theme_mode == ft.ThemeMode.LIGHT else ft.Colors.BLUE_900
                
                if is_dual:
                    if is_right and is_left:
                        trailing_content = ft.Row(
                            [
                                ft.Container(
                                    content=ft.Text("A", color="white", size=self.ui_scale.font(10), weight="bold"),
                                    bgcolor=ft.Colors.INDIGO,
                                    padding=self.ui_scale.px(5),
                                    border_radius=self.ui_scale.px(5),
                                ),
                                ft.Container(
                                    content=ft.Text("B", color="white", size=self.ui_scale.font(10), weight="bold"),
                                    bgcolor=ft.Colors.TEAL,
                                    padding=self.ui_scale.px(5),
                                    border_radius=self.ui_scale.px(5),
                                ),
                            ],
                            spacing=self.ui_scale.px(5),
                        )
                        bg = BG_BOTH
                    elif is_right:
                        trailing_content = ft.Container(
                            content=ft.Text("B", color="white", size=self.ui_scale.font(10), weight="bold"),
                            bgcolor=ft.Colors.TEAL,
                            padding=self.ui_scale.px(5),
                            border_radius=self.ui_scale.px(5),
                        )
                        bg = BG_B
                    elif is_left:
                        trailing_content = ft.Container(
                            content=ft.Text("A", color="white", size=self.ui_scale.font(10), weight="bold"),
                            bgcolor=ft.Colors.INDIGO,
                            padding=self.ui_scale.px(5),
                            border_radius=self.ui_scale.px(5),
                        )
                        bg = BG_A
                else:
                    active_is_selected = is_right if active_slot == "right" else is_left
                    if active_is_selected:
                        check_color = ft.Colors.TEAL if active_slot == "right" else ft.Colors.INDIGO
                        trailing_content = ft.Icon(ft.Icons.CHECK, color=check_color, size=self.ui_scale.px(24))
                        bg = BG_B if active_slot == "right" else BG_A

                if (is_left if list_side == "left" else is_right) and selected_index is None:
                    selected_index = len(target_list.controls)

                favorite_key = self._favorite_key(item)
                hovered = [False]
                favorite = favorite_key in self._favorite_keys
                favorite_button = ft.IconButton(
                    icon=ft.Icons.STAR if favorite else ft.Icons.STAR_BORDER,
                    icon_color=ft.Colors.AMBER_700,
                    icon_size=self.ui_scale.px(19),
                    width=self.ui_scale.px(40),
                    height=self.ui_scale.px(40),
                    padding=self.ui_scale.px(8),
                    tooltip=i18n.get("voice_favorite_remove") if favorite else i18n.get("voice_favorite_add"),
                    visible=favorite,
                    on_click=(lambda e, key=favorite_key: self._on_favorite_clicked(key)) if favorite_key else None,
                )
                if favorite_key is not None:
                    self._favorite_buttons.setdefault(favorite_key, []).append((favorite_button, hovered, list_side))
                favorite_slot = ft.Container(content=favorite_button, width=self.ui_scale.px(40))
                trailing_content = ft.Row(
                    [control for control in (trailing_content, favorite_slot) if control is not None],
                    tight=True, spacing=self.ui_scale.px(4),
                )

                tile = ft.ListTile(
                    leading=ft.Icon(ft.Icons.RECORD_VOICE_OVER, color=ft.Colors.ON_SURFACE, size=self.ui_scale.px(24)),
                    title=ft.Text(display_name, size=self.ui_scale.font(14), weight="w500", no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    trailing=trailing_content,
                    dense=True,
                    content_padding=ft.padding.symmetric(horizontal=self.ui_scale.px(16)),
                    horizontal_spacing=self.ui_scale.px(16),
                    min_leading_width=self.ui_scale.px(40),
                    min_vertical_padding=self.ui_scale.px(4),
                    min_height=self.ui_scale.px(48),
                    data={
                        "name": name,
                        "side": list_side,
                        "sid": item.get("sid") if isinstance(item, dict) else None,
                        "engine": item.get("engine") if isinstance(item, dict) else None,
                    },
                    on_click=self._on_voice_selected,
                    shape=ft.RoundedRectangleBorder(radius=self.ui_scale.px(8)),
                    hover_color=ft.Colors.with_opacity(0.1, "primary"),
                    bgcolor=bg
                )
                def show_favorite(e, button=favorite_button, hover=hovered, key=favorite_key):
                    hover[0] = e.data == "true"
                    button.visible = key is not None and (key in self._favorite_keys or hover[0])
                    self._safe_update(button)

                target_list.controls.append(ft.Container(
                    key=f"voice_{list_side}_{name}", height=self._voice_row_extent,
                    content=tile, alignment=ft.alignment.Alignment(0, 0), on_hover=show_favorite,
                ))

            return selected_index

        rendered_sides = {"left", "right"} if side == "both" else {side}
        self._favorite_buttons = {
            key: [(button, hovered, list_side) for button, hovered, list_side in entries
                  if list_side not in rendered_sides]
            for key, entries in self._favorite_buttons.items()
        }
        selected_indices = {}
            
        if side in ('both', 'left'):
            if not hasattr(self, '_region_positions_left'):
                self._region_positions_left = {}
            selected_indices["left"] = create_tiles(self.list_left, self.region_nav_left, left_voices, self.list_left, self._region_positions_left, "left")

        if side in ('both', 'right'):
            if not hasattr(self, '_region_positions_right'):
                self._region_positions_right = {}
            selected_indices["right"] = create_tiles(self.list_right, self.region_nav_right, right_voices, self.list_right, self._region_positions_right, "right")

        self._selected_voice_indices.update(selected_indices)
        for list_side, index in selected_indices.items():
            if index is None:
                self._voice_focus_pending[list_side] = False
                self._set_voice_edge_padding(list_side, self._voice_list_padding)

        if side == 'both':
            self._safe_update()
        elif side == 'left':
            self._safe_update(self.region_nav_left, self.list_left)
        elif side == 'right':
            self._safe_update(self.region_nav_right, self.list_right)

        if self._is_mounted():
            for list_side in selected_indices:
                list_view = self.list_left if list_side == "left" else self.list_right
                try:
                    if not locate_selected:
                        list_view.scroll_to(offset=saved_offsets[list_side], duration=0)
                except Exception as ex:
                    print(f"DEBUG: Voice list scroll restore skipped: {ex}")
            if locate_selected:
                self.focus_selected_voices(side)
    
    def _scroll_to_region_by_index(self, list_view, index):
        """Scroll to a region section by control index - more reliable for distant items"""
        try:
            list_view.scroll_to(
                offset=self._voice_edge_padding["left" if list_view is self.list_left else "right"]
                + index * self._voice_row_extent,
                duration=300,
            )
            self._host_page.update()
        except Exception as e:
            print(f"DEBUG: Scroll to region by index failed: {e}")

    def _on_voice_selected(self, e):
        data = e.control.data if isinstance(e.control.data, dict) else {"name": e.control.data, "side": None}
        self.selected_voice_name = data.get("name")
        self.selected_voice_side = data.get("side")
        if hasattr(self, 'on_voice_selected'):
            self.on_voice_selected(e)
    
    def _on_text_input_change(self, e):
        """Called when user edits text input - marks text as dirty"""
        current_text = self.text_input.value or ""
        if current_text != self._last_generated_text:
            if hasattr(self, 'on_text_edited'):
                self.on_text_edited(True)  # Notify that text was edited

    # --- Getters ---
    def get_input_text(self):
        return self.text_input.value

    def set_input_text(self, text, mark_as_generated=False):
        """Set text input value. If mark_as_generated=True, this is from a generation."""
        self.text_input.value = text
        if mark_as_generated:
            self._last_generated_text = text
        self._safe_update(self.text_input)
    
    def clean_text_input(self):
        """Remove HTML tags from text input"""
        if not self.text_input.value:
            return
        
        import re
        import html
        # Remove HTML tags using regex
        cleaned = re.sub(r'<[^>]+>', '', self.text_input.value)
        # Also unescape HTML entities to ensure WYSIWYG
        cleaned = html.unescape(cleaned)
        
        if cleaned != self.text_input.value:
            self.text_input.value = cleaned
            self._safe_update(self.text_input)
    
    def is_text_dirty(self):
        """Check if user has edited text since last generation"""
        current_text = self.text_input.value or ""
        return current_text != self._last_generated_text
    
    def show_highlighted_text(self, original_text, word_timings):
        """
        Build highlighted text overlay using precise alignment data.
        """
        self._word_timings = word_timings
        self._original_text = original_text
        self._current_word_index = -1
        self._word_containers = []

        # 长文本逐词构建会显著拖慢点击与切页，超阈值时退化为只读文本模式。
        if len(word_timings or []) > MAX_HIGHLIGHT_WORDS:
            self.highlighted_text_overlay.visible = False
            self.text_input.opacity = 1
            self.text_input.read_only = True
            self._safe_update(self.text_input)
            return
        
        # Lock overlay height to match wrapper
        self._saved_wrapper_height = self.text_input_wrapper.height
        
        # Build overlay content
        self.highlighted_text_column.controls.clear()
        
        font_size = self.ui_scale.font(14)
        word_row = ft.Row(controls=[], wrap=True, spacing=0, run_spacing=0)
        
        # With AlignmentEngine, word_timings now contains "text", "start_char", "end_char"
        # that exact map to original_text substrings.
        # We just need to iterate and fill gaps.
        
        current_char_idx = 0
        
        for i, word_info in enumerate(word_timings):
            start_char = word_info.get("start_char", 0)
            end_char = word_info.get("end_char", 0)
            
            # 1. Fill gap before this word (punctuation, spaces)
            if start_char > current_char_idx:
                between_text = original_text[current_char_idx:start_char]
                if between_text:
                    word_row.controls.append(ft.Text(between_text, size=font_size))
            
            # 2. Add the word itself
            # We use the text from original_text to ensure visual fidelity
            actual_text = original_text[start_char:end_char]
            
            # Safety fallback if indices are weird (shouldn't happen with new engine)
            if not actual_text and word_info.get("text"):
                 actual_text = word_info.get("text")

            word_container = ft.Container(
                content=ft.Text(actual_text, size=font_size),
                padding=0,
                border_radius=self.ui_scale.px(3),
                bgcolor=None,
                data=i, # Store index for reference
                on_click=lambda e, idx=i: self._handle_word_click(idx),
                ink=True, # Visual feedback on hover/click
            )
            
            word_row.controls.append(word_container)
            self._word_containers.append(word_container)
            
            current_char_idx = end_char
        
        # 3. Add trailing text
        if current_char_idx < len(original_text):
            remaining = original_text[current_char_idx:]
            if remaining:
                word_row.controls.append(ft.Text(remaining, size=font_size))
        
        self.highlighted_text_column.controls.append(word_row)
        
        # Overlay Layout Logic (Same as before)
        if self._text_expanded:
            self.highlighted_text_overlay.expand = True
            self.highlighted_text_overlay.height = None
            self.highlighted_text_column.expand = True
            self.highlighted_text_column.height = None
        else:
            overlay_content_height = (
                self._saved_wrapper_height - self.ui_scale.px(24)
                if self._saved_wrapper_height
                else None
            )
            self.highlighted_text_column.height = overlay_content_height
            self.highlighted_text_overlay.height = self._saved_wrapper_height
            self.highlighted_text_overlay.expand = False
            self.highlighted_text_column.expand = False
        
        self.text_input.opacity = 0
        self.text_input.read_only = True
        self.highlighted_text_overlay.visible = True
        self._safe_update(self.text_input, self.highlighted_text_overlay)

    def _handle_word_click(self, word_index):
        """Internal handler to propagate word click event"""
        if hasattr(self, 'on_word_click') and self.on_word_click:
            self.on_word_click(word_index)
    
    def update_highlight_position(self, current_word_index):
        """Update overlay highlighting"""
        if current_word_index == self._current_word_index:
            return
        
        HIGHLIGHT_COLOR = ft.Colors.AMBER_200
        
        if self.highlighted_text_overlay.visible and hasattr(self, '_word_containers') and self._word_containers:
            # Clear previous
            if 0 <= self._current_word_index < len(self._word_containers):
                self._word_containers[self._current_word_index].bgcolor = None
            
            # Set new
            if 0 <= current_word_index < len(self._word_containers):
                container = self._word_containers[current_word_index]
                if container and isinstance(container, ft.Container):
                     container.bgcolor = HIGHLIGHT_COLOR
        
        self._current_word_index = current_word_index
        self._safe_update(self.highlighted_text_overlay)
        
    def hide_highlighted_text(self):
        """Hide overlay and restore text input
        
        关键修复：恢复时重置覆盖层高度，避免残留固定高度影响下次使用
        """
        self.highlighted_text_overlay.visible = False
        self.text_input.opacity = 1
        self.text_input.read_only = False
        self._word_timings = []
        self._word_containers = []
        self._current_word_index = -1
        
        # 关键修复：重置覆盖层高度，恢复动态布局能力
        self.highlighted_text_overlay.height = None
        self.highlighted_text_column.height = None
        
        self._safe_update(self.text_input, self.highlighted_text_overlay)
    
    def set_status(self, message, icon=None, color=None):
        """
        Set status bar message. Pass empty message to hide.
        icon: ft.Icons constant (optional)
        color: background color (optional)
        """
        if not message:
            self._status_text = ""
            self.status_bar.visible = False
            self._safe_update(self.status_bar)
            return

        if message == self._status_text and self.status_bar.visible:
            return
        self._status_text = message
        
        # Update icon and text
        if self.status_bar.content and isinstance(self.status_bar.content, ft.Row):
            icon_control = self.status_bar.content.controls[0]
            text_control = self.status_bar.content.controls[1]
            
            if icon and isinstance(icon_control, ft.Icon):
                icon_control.name = icon
            if isinstance(text_control, ft.Text):
                text_control.value = message
        
        if color:
            self.status_bar.bgcolor = color
        
        self.status_bar.visible = True
        self._safe_update(self.status_bar)

    def get_params(self):
        rate = f"{int(self.rate_slider.value):+d}%"
        volume = f"{int(self.volume_slider.value):+d}%"
        return rate, volume

    def get_selected_voice(self):
        if hasattr(self, 'selected_voice_name'):
            return self.selected_voice_name
        return None

    def _toggle_pin(self, e):
        """Toggle pin (always on top) state"""
        self.btn_pin.selected = not self.btn_pin.selected
        self.btn_pin.update()
        
        is_pinned = self.btn_pin.selected
        print(f"DEBUG: Pin button toggled -> {is_pinned}")
        
        if hasattr(self, 'on_pin_toggle'):
            self.on_pin_toggle(is_pinned)

    def _open_offline_demo(self, e):
        try:
            import webbrowser

            webbrowser.open(KOKORO_MULTI_LANG_V1_1_DOC_URL)
        except Exception as ex:
            print(f"DEBUG: open offline demo failed: {ex}")

    def refresh_texts(self):
        self.input_label_text.value = i18n.get("input_text_label")
        self.header_left.value = i18n.get("voice_list_label_1")
        self.header_right.value = i18n.get("voice_list_label_2")
        self.offline_hint_text.value = i18n.get("offline_voice_hint")
        self.offline_demo_button.text = i18n.get("offline_voice_demo_link", "离线语音音效听")
        self.rate_label_text.value = i18n.get("rate_label")
        self.volume_label_text.value = i18n.get("volume_label")
        self.btn_gen_a.text = i18n.get("generate_button_previous")
        self.btn_replay.tooltip = i18n.get("control_replay", "重播")
        self.btn_play_pause.tooltip = i18n.get("control_play_pause", "播放/暂停")
        self.btn_stop.tooltip = i18n.get("control_stop", "停止")
        self.btn_prev_sentence.tooltip = i18n.get("control_prev_sentence", "上一句")
        self.btn_next_sentence.tooltip = i18n.get("control_next_sentence", "下一句")
        self.btn_pin.tooltip = i18n.get("window_pin", "置顶窗口")
        self.btn_expand_collapse.tooltip = i18n.get("collapse_text_input", "收纳") if self._text_expanded else i18n.get("expand_text_input", "展开")

        if getattr(self, "dual_mode", False):
            self.btn_gen_b.text = i18n.get("generate_button_latest")
        else:
            self.btn_gen_b.text = (
                i18n.get("generate_button_previous")
                if getattr(self, "_single_active_slot", "right") == "left"
                else i18n.get("generate_button_latest")
            )
        self._refresh_favorite_buttons()
        self._safe_update()

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
            print(f"DEBUG: HomeView safe update skipped: {ex}")
