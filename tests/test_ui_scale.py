import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / "Anki-TTS-Flet"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import flet as ft

from config.ui_scale import MAX_UI_SCALE_PERCENT, MIN_UI_SCALE_PERCENT, UiScale
from ui.history_view import HistoryView
from ui.home_view import HomeView
from ui.settings_view import SettingsView


def dummy_page():
    return SimpleNamespace(theme_mode=ft.ThemeMode.LIGHT)


class UiScaleTests(unittest.TestCase):
    def test_supported_range_scales_dimensions_and_fonts(self):
        for percent in (MIN_UI_SCALE_PERCENT, 95, MAX_UI_SCALE_PERCENT):
            with self.subTest(percent=percent):
                scale = UiScale(percent)
                self.assertEqual(scale.px(20), 20 * percent / 100)
                self.assertEqual(scale.font(14), 14 * percent / 100)

    def test_invalid_values_use_100_percent(self):
        for value in (None, True, 80.5, 29, 201, "invalid"):
            with self.subTest(value=value):
                self.assertEqual(UiScale(value).percent, 100)

    def test_views_use_the_same_scale_for_static_dimensions(self):
        compact = UiScale(80)
        home = HomeView(dummy_page(), compact)
        history = HistoryView(dummy_page(), compact)
        settings = SettingsView(dummy_page(), compact)

        self.assertEqual(home.padding, compact.px(20))
        self.assertEqual(home.text_input_wrapper.height, compact.px(140))
        self.assertEqual(home.text_input.text_size, compact.font(14))
        self.assertEqual(home.highlighted_text_overlay.padding, compact.px(12))
        self.assertEqual(home.btn_gen_b.height, compact.px(50))
        self.assertEqual(history.padding, compact.px(20))
        self.assertEqual(history.header_text.size, compact.font(24))
        self.assertEqual(settings.padding, compact.px(20))
        self.assertEqual(settings.header.size, compact.font(24))
        self.assertEqual(settings.ui_scale_input.width, compact.px(120, minimum=90))
        self.assertEqual(settings.ui_scale_input.keyboard_type, ft.KeyboardType.NUMBER)
        self.assertEqual(settings.ui_scale_input.hint_text, "30-200")
        self.assertEqual(settings.ui_scale_input.suffix_text, "%")

        minimum_settings = SettingsView(dummy_page(), UiScale(MIN_UI_SCALE_PERCENT))
        self.assertEqual(minimum_settings.ui_scale_input.width, 90)

    def test_settings_accepts_and_saves_a_custom_scale(self):
        settings = SettingsView(dummy_page())
        saved_settings = []
        settings.on_save_settings = saved_settings.append
        settings._on_ui_scale_input_changed(SimpleNamespace(data="137", control=None))

        settings._on_ui_scale_changed(None)

        self.assertEqual(settings.ui_scale_input.value, "137")
        self.assertEqual(saved_settings[-1]["ui_scale_percent"], 137)

    def test_dynamic_voice_history_and_highlight_controls_are_scaled(self):
        scale = UiScale(120)
        home = HomeView(dummy_page(), scale)
        home.populate_voices(
            [
                {"name": "zh-test", "display_name": "中文", "lang": "zh-CN", "region": "CN"},
                {"name": "en-test", "display_name": "English", "lang": "en-US", "region": "US"},
            ]
        )

        left_region_chip = home.region_nav_left.controls[0]
        left_voice_tile = home.list_left.controls[1].content
        self.assertEqual(left_region_chip.content.size, scale.font(11))
        self.assertEqual(left_voice_tile.title.size, scale.font(14))

        home.show_highlighted_text(
            "你好 hello",
            [
                {"text": "你好", "start_char": 0, "end_char": 2},
                {"text": "hello", "start_char": 3, "end_char": 8},
            ],
        )
        highlight_row = home.highlighted_text_column.controls[0]
        highlighted_words = [
            control.content
            for control in highlight_row.controls
            if isinstance(control, ft.Container)
        ]
        self.assertTrue(highlighted_words)
        self.assertTrue(all(text.size == scale.font(14) for text in highlighted_words))
        self.assertEqual(
            home.highlighted_text_column.height,
            scale.px(140) - scale.px(24),
        )

        history = HistoryView(dummy_page(), scale)
        history.populate_history(
            [{"text": "example", "voice": "en-test", "timestamp": 1, "path": "unused.mp3"}]
        )
        history_card = history.history_list.controls[0]
        text_column = history_card.content.controls[1]
        self.assertEqual(history_card.padding, scale.px(10))
        self.assertEqual(text_column.controls[0].size, scale.font(14))
        self.assertEqual(text_column.controls[1].size, scale.font(12))

    def test_voice_favorites_are_shared_without_selecting_a_voice(self):
        home = HomeView(dummy_page())
        home.populate_voices([
            {"name": "zh-test", "lang": "zh-CN", "region": "CN"},
        ])
        callback = Mock()
        home.on_favorite_toggled = callback
        home.on_voice_selected = Mock()
        key = "edge_online:zh-test"
        left_button = home._favorite_buttons[key][0][0]
        right_button = home._favorite_buttons[key][1][0]
        self.assertFalse(left_button.visible)
        left_row = home.list_left.controls[1]
        left_row.on_hover(SimpleNamespace(data="true"))
        self.assertTrue(left_button.visible)
        self.assertFalse(right_button.visible)
        left_row.on_hover(SimpleNamespace(data="false"))
        self.assertFalse(left_button.visible)
        left_button.on_click(None)
        callback.assert_called_once_with(key, True)
        home.on_voice_selected.assert_not_called()
        self.assertEqual(left_button.icon, ft.Icons.STAR)
        self.assertEqual(right_button.icon, ft.Icons.STAR)
        self.assertTrue(left_button.visible)
        self.assertTrue(right_button.visible)
        home._on_filter_change("left")
        right_button_after_left_refresh = home._favorite_buttons[key][0][0]
        left_button_after_refresh = home._favorite_buttons[key][1][0]
        self.assertIs(right_button_after_left_refresh, right_button)
        right_button.on_click(None)
        self.assertNotIn(key, home._favorite_keys)
        self.assertFalse(left_button_after_refresh.visible)
        self.assertFalse(right_button.visible)

    def test_voice_scroll_restores_saved_offset_or_locates_selected_voice(self):
        home = HomeView(dummy_page())
        voices = [
            {"name": f"zh-{index}", "lang": "zh-CN", "region": "CN"}
            for index in range(10)
        ]
        home.populate_voices(voices)
        home.list_left.on_scroll(SimpleNamespace(pixels=73.0))
        home.list_right.on_scroll(SimpleNamespace(pixels=29.0))
        self.assertEqual(home._voice_scroll_offsets, {"left": 73.0, "right": 29.0})
        home._is_mounted = lambda: True
        home._safe_update = lambda *controls: home._voice_scroll_offsets.update(left=0, right=0)
        home.list_left.scroll_to = Mock()
        home.list_right.scroll_to = Mock()

        home.set_selections("zh-4", "zh-1")
        home.list_left.scroll_to.assert_called_with(offset=1, duration=0)
        home.list_right.scroll_to.assert_called_with(offset=1, duration=0)
        viewport = home._voice_row_extent * 5
        home.list_left.on_scroll(SimpleNamespace(pixels=1.0, viewport_dimension=viewport))
        home.list_right.on_scroll(SimpleNamespace(pixels=1.0, viewport_dimension=viewport))
        self.assertFalse(home._voice_focus_pending["left"])
        self.assertFalse(home._voice_focus_pending["right"])
        self.assertEqual(home._selected_voice_indices, {"left": 5, "right": 2})
        edge_padding = (viewport - home._voice_row_extent) / 2
        self.assertEqual(home.list_left.padding.top, edge_padding)
        self.assertEqual(home.list_right.padding.bottom, edge_padding)
        self.assertEqual(home.list_left.scroll_to.call_args.kwargs["offset"], home._voice_row_extent * 5)

        home.list_left.scroll_to.reset_mock()
        home.list_right.scroll_to.reset_mock()
        home._voice_scroll_offsets = {"left": 73.0, "right": 29.0}
        home.set_selections("zh-0", "zh-9")
        home.list_left.scroll_to.assert_called_with(offset=73.0, duration=0)
        home.list_right.scroll_to.assert_called_with(offset=29.0, duration=0)

        home.focus_selected_voices()
        home.list_left.scroll_to.assert_called_with(offset=home._voice_row_extent, duration=0)
        max_offset = len(home.list_right.controls) * home._voice_row_extent + 2 * edge_padding - viewport
        home.list_right.scroll_to.assert_called_with(offset=max_offset, duration=0)

    def test_kokoro_favorite_key_uses_catalog_version_and_sid(self):
        self.assertEqual(
            HomeView._favorite_key({"name": "voice", "sid": 12}),
            "local_kokoro:v1_1:12",
        )

    def test_voice_rows_have_fixed_extent_at_supported_ui_scales(self):
        for percent in (MIN_UI_SCALE_PERCENT, 100, MAX_UI_SCALE_PERCENT):
            with self.subTest(percent=percent):
                home = HomeView(dummy_page(), UiScale(percent))
                home.populate_voices([{"name": "long-voice-name" * 10, "lang": "zh-CN", "region": "CN"}])
                row = home.list_left.controls[1]
                self.assertEqual(home.list_left.item_extent, home._voice_row_extent)
                self.assertEqual(row.height, home._voice_row_extent)
                self.assertGreaterEqual(row.height, 54)
                self.assertEqual(row.content.title.overflow, ft.TextOverflow.ELLIPSIS)
                star = home._favorite_buttons["edge_online:" + "long-voice-name" * 10][0][0]
                self.assertLess(star.icon_size, row.height)

    def test_filter_keeps_language_when_selected_voice_is_elsewhere(self):
        home = HomeView(dummy_page())
        home.populate_voices([
            {"name": "zh-test", "lang": "zh-CN", "region": "CN"},
            {"name": "en-test", "lang": "en-US", "region": "US"},
        ])
        home.set_selections("en-test", "en-test")
        self.assertEqual(home.lang_dropdown_left.value, "zh-CN")
        self.assertEqual(len(home.list_left.controls), 2)
        self.assertEqual(home.list_left.controls[1].content.data["name"], "zh-test")
        home._is_mounted = lambda: True
        home.list_left.scroll_to = Mock()
        home.list_right.scroll_to = Mock()
        home.focus_selected_voices()
        home.list_left.scroll_to.assert_not_called()
        home.list_right.scroll_to.assert_called_once_with(offset=1, duration=0)
        self.assertEqual(home.list_left.padding, home._voice_list_padding)

    def test_short_window_layout_keeps_voice_area_in_scrollable_content(self):
        scale = UiScale(80)
        home = HomeView(dummy_page(), scale)

        home.set_compact_height_layout(True)
        self.assertEqual(home.content.scroll, ft.ScrollMode.AUTO)
        self.assertFalse(home.voice_area.expand)
        self.assertEqual(home.voice_area.height, scale.px(190))

        home.set_compact_height_layout(False)
        self.assertIsNone(home.content.scroll)
        self.assertTrue(home.voice_area.expand)
        self.assertIn(home.voice_area.height, (None, ""))


if __name__ == "__main__":
    unittest.main()
