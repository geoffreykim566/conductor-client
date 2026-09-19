"""T6 — open ANY plugin by name (the primitive). Three mechanisms:
  (a) Search-and-Add-Plug-in: Ctrl+Cmd+P, type the name, Return  (audio FX only;
      dialog is kCGWindowLayer 25 — invisible to OCR, but we verify via AX: the
      selected strip's empty 'audio plug-in' AXButton becomes an AXGroup named
      after the plugin, and a plugin AXWindow appears)
  (b) insert-slot menu: AXPress the empty slot button (returns -25204 but opens),
      then drill the category tree by AXPress on titles
  (c) instrument slot: same drill on the software-instrument track's slot.
Usage: python -m tests.ax_mechanics.t6_open_plugin [a|b|c|all]
"""
import sys, time
import ApplicationServices as AS
from tests.ax_mechanics._ax_common import *

SEARCH_NAMES = ["Phat FX", "Step FX", "Vintage Console EQ", "ValhallaSupermassive"]   # none in the KB
MENU_PATHS = [("Multi Effects", "Phat FX"), ("Audio Units", "Valhalla DSP", "ValhallaSupermassive")]
INSTRUMENT_PATH = ("Synthesizer", "ES2 (Synthesizer 2)")


def strip(mw, name):
    mixer = find_anywhere(mw, desc_="Mixer", role_="AXLayoutArea")
    return find_child(mixer, AS.kAXDescriptionAttribute, name, "AXLayoutItem") if mixer else None


def select_track(mw, name):
    h = track_header(mw, name)
    click_at(*center(find_child(h, AS.kAXDescriptionAttribute, name, "AXTextField") or h))
    wait_until(lambda: strip(mw, name), timeout=3.0)


def fx_slots(mw, track):
    """(empty_button, loaded_groups) on the track's channel strip."""
    s = strip(mw, track)
    empty = find_child(s, AS.kAXDescriptionAttribute, "audio plug-in", "AXButton") if s else None
    loaded = [c for c in children(s or [] and s) if role(c) == "AXGroup" and
              {"bypass", "open", "list"} <= {desc(k) for k in children(c)}] if s else []
    return empty, loaded


def loaded_names(mw, track):
    return [desc(g) for g in fx_slots(mw, track)[1]]


def remove_plugin(app, mw, track, name):
    """Open the loaded slot's 'list' menu and choose 'No Plug-in'."""
    key = name.lower().replace(" ", "")[:6]
    g = next((g for g in fx_slots(mw, track)[1] if (desc(g) or "").lower().replace(" ", "").startswith(key)), None)
    if g is None:
        return False
    lst = find_child(g, AS.kAXDescriptionAttribute, "list", "AXButton")
    ax_press(lst); time.sleep(0.5)
    menu = current_menu(app, center(lst))
    item = next((i for i in children(menu) if (title(i) or "").startswith("No Plug-in")), None) if menu else None
    if item is None:
        press("Escape"); return False
    ax_press(item)
    gone, _ = wait_until(lambda: (not any((n or "").lower().replace(" ", "").startswith(key) for n in loaded_names(mw, track))) or None, timeout=3.0)
    return bool(gone)


def current_menu(app, point=None):
    """The open AXMenu: focused element's ancestor, or element-at-point's parent."""
    f = focused(app)
    node = f
    for _ in range(6):
        if node is None: break
        if role(node) == "AXMenu": return node
        node = ax_get(node, AS.kAXParentAttribute)
    if point:
        el = element_at(*point)
        p = ax_get(el, AS.kAXParentAttribute) if el is not None else None
        if p is not None and role(p) == "AXMenu": return p
    return None


def drill(app, menu, path):
    """AXPress each hop; a hop with a submenu exposes it as AXMenuItem -> [AXMenu]."""
    for hop in path:
        items = children(menu)
        item = next((i for i in items if (title(i) or "").strip() == hop), None) or \
               next((i for i in items if hop.lower() in (title(i) or "").lower()), None)
        if item is None:
            print(f"    hop {hop!r} not found; items: {[title(i) for i in items][:25]}")
            return False
        code = ax_press(item); time.sleep(0.45)
        sub, _ = wait_until(lambda: next((c for c in children(item) if role(c) == "AXMenu" and children(c)), None), timeout=1.5 if hop != path[-1] else 0.8)
        if hop != path[-1]:
            if sub is None:
                print(f"    submenu for {hop!r} did not populate (press code={code})"); return False
            menu = sub
        elif sub is not None:
            # Terminal item still has a submenu (e.g. Mono / Stereo / Mono->Stereo on a mono
            # strip, or Stereo / Multi-Output on Drum Kit Designer) -- the July "silent false
            # success" trap. Prefer 'Stereo', else the first entry.
            subs = [c for c in children(sub) if title(c)]
            pick = next((c for c in subs if title(c) == "Stereo"), subs[0] if subs else None)
            print(f"    terminal {hop!r} has sub-choices {[title(c) for c in subs]}; picking {title(pick)!r}")
            if pick is None: return False
            ax_press(pick); time.sleep(0.45)
    return True


def window_plugin_name(app, before):
    """Plugin windows are titled after the track; the plugin's name is the first
    AXStaticText in the window (the header's plugin-name popup)."""
    for w in app_windows(app):
        if title(w) not in before:
            g = next((c for c in children(w) if role(c) == "AXGroup" and title(c)), None)
            if g is not None:
                return title(g)
            texts = [value(e) for e in find_all(w, lambda e: role(e) == "AXStaticText" and value(e), maxd=6)]
            texts = [t for t in texts if t not in ("View:", title(w))]
            return texts[-1] if texts else None
    return None


def plugin_window(app, name, before):
    got, dt = wait_until(lambda: (window_titles(app) - before) or None, timeout=4.0)
    return got, dt


def open_via_search(app, mw, track, name):
    before_w = window_titles(app); before_n = loaded_names(mw, track)
    assert_frontmost("before Ctrl+Cmd+P"); press("Ctrl+Cmd+P"); time.sleep(0.45)
    f = focused(app)
    if f is None or role(f) != "AXTextField":
        result(f"(a) search {name}", False, f"search field not focused: {role(f)!r}"); return False
    ax_set(f, AS.kAXValueAttribute, name)          # type into the field via AX instead of per-letter keystrokes
    time.sleep(0.6)
    typed = value(focused(app))
    press("Return")
    got, dt = wait_until(lambda: [n for n in loaded_names(mw, track) if n not in before_n] or None, timeout=5.0)
    newwin, _ = plugin_window(app, name, before_w)
    shown = window_plugin_name(app, before_w)
    ok = bool(got) and shown is not None and name.lower().replace(" ", "") in shown.lower().replace(" ", "")
    result(f"(a) search {name!r}", ok, f"typed={typed!r}; slot label {got}; window shows {shown!r}; new windows={newwin} ({dt:.2f}s)")
    return got[0] if got else None


def open_via_slot_menu(app, mw, track, path):
    before_n = loaded_names(mw, track)
    empty, _ = fx_slots(mw, track)
    if empty is None:
        result(f"(b) {' > '.join(path)}", False, "no empty slot"); return None
    c = center(empty); assert_frontmost("before slot press")
    code = ax_press(empty); time.sleep(0.6)
    menu = current_menu(app, c)
    if menu is None:
        click_at(*c); time.sleep(0.6); menu = current_menu(app, c); how = f"AXPress code={code} no menu -> click_at"
    else:
        how = f"AXPress code={code} (menu opened regardless)"
    if menu is None:
        result(f"(b) {' > '.join(path)}", False, how + "; still no AXMenu"); return None
    ok = drill(app, menu, path)
    got, dt = wait_until(lambda: [n for n in loaded_names(mw, track) if n not in before_n] or None, timeout=5.0)
    if not ok: press("Escape")
    result(f"(b) {' > '.join(path)}", bool(got), f"{how}; drill={ok}; slot now {got} ({dt:.2f}s)")
    return got[0] if got else None


def open_instrument(app, mw, track, path):
    s = strip(mw, track)
    is_slot = lambda c: role(c) == "AXGroup" and {"bypass", "open", "list"} <= {desc(k) for k in children(c)}
    inst = next((c for c in children(s) if is_slot(c)), None) if s else None
    if inst is None:
        result("(c) instrument slot", False, "no instrument slot group with a list button"); return None
    lst = find_child(inst, AS.kAXDescriptionAttribute, "list", "AXButton")
    before = desc(inst); c = center(lst)
    code = ax_press(lst); time.sleep(0.6)
    menu = current_menu(app, c)
    if menu is None:
        result("(c) instrument menu", False, f"AXPress code={code}, no menu"); return None
    ok = drill(app, menu, path)
    got, dt = wait_until(lambda: (desc(next((c for c in children(strip(mw, track)) if is_slot(c)), None)) != before) or None, timeout=6.0)
    if not ok: press("Escape")
    result(f"(c) {' > '.join(path)}", bool(got), f"AXPress code={code}; drill={ok}; slot {before!r} -> {got!r} ({dt:.2f}s)")
    return got


def close_plugin_windows(app, base):
    for w in app_windows(app):
        if title(w) not in base:
            close_window(w)
    wait_until(lambda: (window_titles(app) == base) or None, timeout=3.0)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    banner(f"T6 open any plugin [{which}]")
    app = app_element(); bring_logic_front(); mw = main_window(app)
    base = wait_for_settle(app)
    select_track(mw, "Audio 1")
    print("  Audio 1 loaded FX:", loaded_names(mw, "Audio 1"))
    if which in ("a", "all"):
        for name in SEARCH_NAMES:
            got = open_via_search(app, mw, "Audio 1", name)
            time.sleep(0.5); close_plugin_windows(app, base)
            if got:
                result(f"    remove {got!r}", remove_plugin(app, mw, "Audio 1", got), "via slot list > No Plug-in")
            time.sleep(0.5)
    if which in ("b", "all"):
        for path in MENU_PATHS:
            got = open_via_slot_menu(app, mw, "Audio 1", path)
            time.sleep(0.5); close_plugin_windows(app, base)
            if got:
                result(f"    remove {got!r}", remove_plugin(app, mw, "Audio 1", got), "via slot list > No Plug-in")
            time.sleep(0.5)
    if which in ("c", "all"):
        select_track(mw, "Deluxe Classic")
        open_instrument(app, mw, "Deluxe Classic", INSTRUMENT_PATH)
        time.sleep(0.5); close_plugin_windows(app, base)
        select_track(mw, "Audio 1")
    print("  final windows:", window_titles(app), "| Audio 1 FX:", loaded_names(mw, "Audio 1"))


if __name__ == "__main__":
    main()
