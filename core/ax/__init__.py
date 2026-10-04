"""Accessibility-API toolkit for driving Logic Pro directly (no OCR).

Import the package and use the flat namespace (`from core import ax`;
`ax.select_track(...)`). Submodules only import downward (primitives ->
search/app/mouse -> menus/channel_strip -> plugins/params/tracks) and from
core.events; nothing here imports core.automation. See README.md.
"""
from core.ax.primitives import (
    CANNOT_COMPLETE, SETTLE_S, VERIFY_TIMEOUT_S, AxError, ax_get, ax_press, ax_set, center,
    children, desc, element_at, norm, parent, role, title, value, wait_until,
)
from core.ax.search import find_all, find_anywhere, find_child
from core.ax.app import (
    app_element, app_windows, ensure_on_screen, focused, logic_pid, main_window, raise_window,
    window_titles,
)
from core.ax.mouse import click_at, double_click_at, press_or_click
from core.ax.menus import current_menu, dismiss_menus, drill, menu_item_checked, menubar_item, open_menu_of
from core.ax.channel_strip import fx_slots, loaded_names, loaded_slot, selected_strip, strip
from core.ax.plugin_windows import plugin_window_for, plugin_windows_seen, window_plugin_name
from core.ax.plugins import open_loaded_plugin, open_plugin_by_search, remove_plugin
from core.ax.controls_view import (
    OFF, ON, match_param, num, param_rows, read_param, set_view, slider_range, write_param_bool,
    write_param_display, write_param_raw,
)
from core.ax.editor_view import (
    editor_checkbox, editor_labelled_slider, set_editor_checkbox, type_param_value,
)
from core.ax.tracks import select_track, track_header

__all__ = [
    "app_element",
    "app_windows",
    "ax_get",
    "ax_press",
    "ax_set",
    "AxError",
    "CANNOT_COMPLETE",
    "center",
    "children",
    "click_at",
    "current_menu",
    "desc",
    "dismiss_menus",
    "double_click_at",
    "drill",
    "editor_checkbox",
    "editor_labelled_slider",
    "element_at",
    "ensure_on_screen",
    "find_all",
    "find_anywhere",
    "find_child",
    "focused",
    "fx_slots",
    "loaded_names",
    "loaded_slot",
    "logic_pid",
    "main_window",
    "match_param",
    "menu_item_checked",
    "menubar_item",
    "norm",
    "num",
    "OFF",
    "ON",
    "open_loaded_plugin",
    "open_menu_of",
    "open_plugin_by_search",
    "param_rows",
    "parent",
    "plugin_window_for",
    "plugin_windows_seen",
    "press_or_click",
    "raise_window",
    "read_param",
    "remove_plugin",
    "role",
    "select_track",
    "selected_strip",
    "set_editor_checkbox",
    "set_view",
    "SETTLE_S",
    "slider_range",
    "strip",
    "title",
    "track_header",
    "type_param_value",
    "value",
    "VERIFY_TIMEOUT_S",
    "wait_until",
    "window_plugin_name",
    "window_titles",
    "write_param_bool",
    "write_param_display",
    "write_param_raw",
]
