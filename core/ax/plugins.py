"""Add, open and remove plugins on the selected channel strip."""
from __future__ import annotations

import time

import ApplicationServices as AS

from core.ax.app import ensure_on_screen, focused
from core.ax.channel_strip import fx_slots, loaded_names, loaded_slot, selected_strip
from core.ax.menus import dismiss_menus, open_menu_of
from core.ax.plugin_windows import plugin_window_for, plugin_windows_seen
from core.ax.primitives import AxError, ax_press, ax_set, children, role, title, wait_until
from core.ax.search import find_child
from core.events.keyboard import press


def open_plugin_by_search(app, mw, name: str, stop_check=None) -> tuple[str, object, int]:
    """Search-and-Add-Plug-in on the selected strip: Ctrl+Cmd+P, set the search
    field's AXValue, Return. Returns (slot_label, plugin_window). Verifies by the
    plugin window's own name, never the truncated slot label."""
    s = selected_strip(mw)
    before_w = plugin_windows_seen(app)
    before_n = loaded_names(s)
    press("Ctrl+Cmd+P")
    f, _ = wait_until(lambda: (lambda x: x if x is not None and role(x) == "AXTextField" else None)(focused(app)), timeout=2.0)
    if f is None:
        raise AxError("Search-and-Add-Plug-in field did not take focus")
    ax_set(f, AS.kAXValueAttribute, name)
    time.sleep(0.5)
    press("Return")
    # count-based: a second instance of an already-loaded plugin has the same label
    got, _ = wait_until(lambda: (lambda n: n if len(n) > len(before_n) else None)(loaded_names(selected_strip(mw))), timeout=5.0)
    if not got:
        dismiss_menus(app)
        raise AxError(f"no plugin loaded for {name!r}")
    new_idx = next((i for i, n in enumerate(got) if i >= len(before_n) or n != before_n[i]), len(got) - 1)
    win, _ = wait_until(lambda: plugin_window_for(app, name, before_w), timeout=4.0)
    if win is None:
        # Report and leave the slot alone; never auto-remove here (see README
        # "Plugin load mismatch"). The ledger entry is what undoes a load.

        raise AxError(f"search loaded {got[new_idx]!r}, whose window did not come up as {name!r}")
    ensure_on_screen(win)
    return got[new_idx], win, new_idx


def open_loaded_plugin(app, mw, name: str, index: int | None = None, track: str | None = None):
    """Open the window of an already-loaded plugin via its slot's 'open' button.
    `track`: the selected strip's track, so another track's open window of the
    same plugin isn't taken for this one."""
    g = loaded_slot(selected_strip(mw), name, index)
    if g is None:
        return None
    before_w = plugin_windows_seen(app)
    win = plugin_window_for(app, name, track=track)
    if win is None:
        ax_press(find_child(g, AS.kAXDescriptionAttribute, "open", "AXButton"))
        win, _ = wait_until(lambda: plugin_window_for(app, name, before_w, track=track), timeout=4.0)
    if win is not None:
        ensure_on_screen(win)
    return win


def remove_plugin(app, mw, slot_label: str, index: int | None = None) -> bool:
    """Open the loaded slot's 'list' menu and choose 'No Plug-in'."""
    s = selected_strip(mw)
    g = loaded_slot(s, slot_label, index)
    if g is None:
        return False
    n_before = len(fx_slots(s)[1])
    lst = find_child(g, AS.kAXDescriptionAttribute, "list", "AXButton")
    menu = open_menu_of(app, lst)
    item = next((i for i in children(menu) if (title(i) or "").startswith("No Plug-in")), None) if menu else None
    if item is None:
        dismiss_menus(app)
        return False
    ax_press(item)
    gone, _ = wait_until(lambda: (len(fx_slots(selected_strip(mw))[1]) < n_before) or None, timeout=3.0)
    return bool(gone)
