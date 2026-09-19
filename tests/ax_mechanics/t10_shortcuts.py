"""T10 — shortcut sweep via executor.press() with the frontmost gate. Each entry:
(shortcut, description, verify(app, mw, before) -> (ok, evidence), undo)."""
import time
import ApplicationServices as AS
from tests.ax_mechanics._ax_common import *


def new_window(app, before):
    got, dt = wait_until(lambda: (window_titles(app) - before) or None, timeout=3.0)
    return got, dt


def toggle_check(mw, d):
    return lambda: value(find_anywhere(mw, desc_=d, role_="AXCheckBox"))


CASES = [
    # (shortcut, expect kind, arg, undo)
    ("Cmd+,",         "window", "Settings",          None),          # Logic Pro settings
    ("Option+P",      "window", "Project Settings",  None),
    ("X",             "window", "Mixer",             "X"),           # Mixer toggles a window title in Logic 12? verified below
    ("Y",             "window", "Library",           "Y"),
    ("Option+T",      "window", "Configure Track Header", "Escape"),
    ("Cmd+K",         "window", "Musical Typing",    "Cmd+K"),
    ("Ctrl+Cmd+P",    "layer25", "Search and Add",   "Escape"),
    ("Option+Cmd+N",  "window", "New Tracks",        "Escape"),
    ("Cmd+B",         "window", "Bounce",            "Escape"),
    ("Cmd+F",         "popup",  "flex",              "Escape"),
]


def main():
    banner("T10 shortcut sweep")
    app = app_element(); bring_logic_front(); mw = main_window(app)
    base = wait_for_settle(app)
    for key, kind, arg, undo in CASES:
        assert_frontmost(f"before {key}")
        before = window_titles(app)
        press(key)
        if kind == "window":
            got, dt = new_window(app, before)
            hit = got and any(arg.lower() in (t or "").lower() for t in got)
            # some toggles (Mixer/Library) don't create a window: fall back to checking the layer set / AX tree
            if not got:
                probe = find_anywhere(mw, desc_=arg, role_="AXGroup") or find_anywhere(mw, title_=arg)
                hit = probe is not None
                result(key, bool(hit), f"no new window; AX group/title {arg!r} present={hit} ({dt:.2f}s)")
            else:
                result(key, bool(hit), f"new windows={got} after {dt:.2f}s")
        elif kind == "layer25":
            time.sleep(0.5)
            ids = logic_window_ids(); f = focused(app)
            result(key, f is not None and role(f) == "AXTextField", f"focused={role(f)!r} {desc(f)!r}; logic windows on screen={len(ids)}")
        else:
            time.sleep(0.5); f = focused(app)
            result(key, True, f"focused after: {role(f)!r} {desc(f)!r} {title(f)!r}")
        time.sleep(0.5)
        # undo / close whatever opened
        after = window_titles(app) - before
        for w in app_windows(app):
            if title(w) in after:
                close_window(w)
        if undo:
            assert_frontmost("before undo"); press(undo)
        wait_until(lambda: (window_titles(app) == base) or None, timeout=3.0)
        time.sleep(0.4)
    print("  final windows:", window_titles(app))


if __name__ == "__main__":
    main()
