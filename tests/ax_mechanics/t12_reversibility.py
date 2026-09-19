"""T12 — which actions does Logic's own Undo revert? For each action class:
do it via AX, read the Edit menu's 'Undo …' item title (queryable without
opening the menu), press Cmd+Z, verify the state came back via AX."""
import time
import ApplicationServices as AS
from tests.ax_mechanics._ax_common import *
from tests.ax_mechanics.t6_open_plugin import (open_via_search, remove_plugin, select_track,
                                               loaded_names, close_plugin_windows, current_menu, strip)
from tests.ax_mechanics.t7_set_param import set_view, rows, plugin_win


def undo_title(app):
    mb = ax_get(app, AS.kAXMenuBarAttribute)
    edit = find_child(mb, AS.kAXTitleAttribute, "Edit")
    for it in find_all(edit, lambda e: role(e) == "AXMenuItem", maxd=3):
        if (title(it) or "").startswith("Undo"):
            return title(it)
    return None


def undo(app):
    assert_frontmost("before Cmd+Z"); press("Cmd+Z"); time.sleep(0.6)


def check(app, name, do, is_done, is_reverted):
    t0 = undo_title(app)
    do()
    ok, dt = wait_until(lambda: is_done() or None, timeout=3.0)
    t1 = undo_title(app)
    if not ok:
        result(name, None, f"action itself didn't take ({dt:.2f}s) — skipped"); return
    undo(app)
    back, dt2 = wait_until(lambda: is_reverted() or None, timeout=3.0)
    result(name, bool(back), f"Undo item before={t0!r} after={t1!r}; Cmd+Z reverted={bool(back)} ({dt2:.2f}s)")
    return bool(back)


def main():
    banner("T12 reversibility via Logic Undo")
    app = app_element(); bring_logic_front(); mw = main_window(app); base = wait_for_settle(app)
    select_track(mw, "Audio 1")
    hdr = lambda: track_header(mw, "Audio 1")
    mute = lambda: find_child(hdr(), AS.kAXDescriptionAttribute, "Mute")
    vol = lambda: find_child(hdr(), AS.kAXDescriptionAttribute, "Volume", "AXSlider")

    # 1 mute (real click)
    r = check(app, "mute", lambda: click_at(*center(mute())), lambda: value(mute()) == 1, lambda: value(mute()) == 0)
    if r is False: click_at(*center(mute())); time.sleep(0.3)
    # 2 volume via text field
    v0 = value(vol())
    r = check(app, "volume -6 dB", lambda: set_via_text_field(app, vol(), "-6.0"), lambda: value(vol()) != v0, lambda: value(vol()) == v0)
    if r is False: set_via_text_field(app, vol(), "+0.0"); time.sleep(0.3)
    # 3 rename
    name_el = lambda n: find_child(track_header(mw, n), AS.kAXDescriptionAttribute, n, "AXTextField")
    r = check(app, "rename", lambda: set_via_text_field(app, name_el("Audio 1"), "Undo Me"), lambda: track_header(mw, "Undo Me"), lambda: track_header(mw, "Audio 1"))
    if r is False: set_via_text_field(app, name_el("Undo Me"), "Audio 1"); time.sleep(0.3)
    # 4 insert plugin
    r = check(app, "insert Channel EQ", lambda: open_via_search(app, mw, "Audio 1", "Channel EQ"),
              lambda: loaded_names(mw, "Audio 1"), lambda: not loaded_names(mw, "Audio 1"))
    close_plugin_windows(app, base)
    if r is False: remove_plugin(app, mw, "Audio 1", "Channel EQ"); time.sleep(0.3)
    # 5 plugin parameter via Controls view
    open_via_search(app, mw, "Audio 1", "Channel EQ"); wait_until(lambda: plugin_win(app, base), timeout=4.0); time.sleep(0.8)
    set_view(app, plugin_win(app, base), "Controls"); time.sleep(0.4)
    def sl():
        w = plugin_win(app, base)
        r = rows(w) if w is not None else {}
        return r["Peak 1 Gain"][1] if "Peak 1 Gain" in r else None
    p0 = value(sl())
    def param_state():
        w = plugin_win(app, base); s = sl()
        return f"window={title(w) if w else None} loaded={loaded_names(mw, 'Audio 1')} raw={value(s) if s is not None else None}"
    check(app, "plugin param (Peak 1 Gain +60 raw)", lambda: ax_set(sl(), AS.kAXValueAttribute, float(p0) + 60.0),
          lambda: sl() is not None and value(sl()) == float(p0) + 60.0,
          lambda: sl() is not None and value(sl()) == float(p0))
    print("   state after undo:", param_state())
    if plugin_win(app, base) is not None:
        set_view(app, plugin_win(app, base), "Editor"); close_plugin_windows(app, base)
    if not loaded_names(mw, "Audio 1"):
        print("   (plugin gone after undo — re-inserting Channel EQ for step 6)")
        open_via_search(app, mw, "Audio 1", "Channel EQ"); time.sleep(0.5); close_plugin_windows(app, base)
    # 6 remove plugin
    r = check(app, "remove plugin", lambda: remove_plugin(app, mw, "Audio 1", "Channel EQ"),
              lambda: not loaded_names(mw, "Audio 1"), lambda: loaded_names(mw, "Audio 1"))
    close_plugin_windows(app, base)
    if r: remove_plugin(app, mw, "Audio 1", "Channel EQ"); time.sleep(0.3)   # leave the strip clean
    # 7 delete track (Audio 2, empty): select header then Delete key; handle any confirm sheet
    def del_track():
        select_track(mw, "Audio 2"); time.sleep(0.3); assert_frontmost("before Delete"); press("Delete"); time.sleep(0.5)
        sheet = next((c for c in children(mw) if role(c) == "AXSheet"), None)
        if sheet is not None:
            btn = next((b for b in find_all(sheet, lambda e: role(e) == "AXButton", maxd=6) if (title(b) or "") in ("Delete", "OK")), None)
            print("   confirm sheet:", [title(b) for b in find_all(sheet, lambda e: role(e) == 'AXButton', maxd=6)])
            if btn is not None: ax_press(btn)
    check(app, "delete track Audio 2", del_track, lambda: track_header(mw, "Audio 2") is None, lambda: track_header(mw, "Audio 2") is not None)
    select_track(mw, "Audio 1")
    print("  final tracks:", [desc(h) for h in track_headers(mw)], "| Audio 1 FX:", loaded_names(mw, "Audio 1"), "| windows:", window_titles(app))


if __name__ == "__main__":
    main()
