"""T7 — set a plugin parameter to an exact value, two mechanisms:

  editor view : named AXSlider (only some Apple plugins label these — Channel EQ
                26/26, Compressor 1/22, Tape Delay 0/14, third-party 0) via
                double-click -> focused AXTextField -> set -> Return.
  Controls view: UNIVERSAL. Switch the plugin window's View menu to 'Controls';
                every parameter becomes an AXCell {AXStaticText 'Label:',
                AXGroup readout, AXSlider}. A direct AXValue write on that slider
                lands exactly (found 2026-09-18 — the July "direct write clamps"
                finding was the track fader only). Verify by re-reading raw value
                and the readout text.

Usage: python -m tests.ax_mechanics.t7_set_param ["Plugin Name" ...]
"""
import sys, time
import ApplicationServices as AS
from tests.ax_mechanics._ax_common import *
from tests.ax_mechanics.t6_open_plugin import (open_via_search, remove_plugin, select_track,
                                               close_plugin_windows, current_menu)

# plugin -> (editor-view slider desc, editor target text, controls-view row label, raw delta)
TARGETS = {
    "Channel EQ":           ("Peak 1 Gain", "6.0",   "Peak 1 Gain", 60.0),
    "Compressor":           ("Threshold",   "-18.0", "Threshold",   4.0),
    "Tape Delay":           (None,          None,    "Feedback",    10.0),
    "ValhallaSupermassive": (None,          None,    "Mix",         1000.0),
}


def plugin_win(app, base):
    return next((w for w in app_windows(app) if title(w) not in base), None)


def set_view(app, win, name):
    btn = next((c for c in children(win) if role(c) == "AXMenuButton" and desc(c) == "view"), None)
    if btn is None:
        return False
    c = center(btn); ax_press(btn); time.sleep(0.6)
    menu = next((k for k in children(btn) if role(k) == "AXMenu"), None) or current_menu(app, c)
    it = next((i for i in children(menu) if title(i) == name), None) if menu else None
    if it is None:
        press("Escape"); return False
    ax_press(it); time.sleep(1.0); return True


def rows(win):
    """Controls view: label -> (cell, slider, readout)."""
    out = {}
    for cell in find_all(win, lambda e: role(e) == "AXCell", maxd=14):
        kids = children(cell)
        lab = next((value(k) for k in kids if role(k) == "AXStaticText"), None)
        sl = next((k for k in kids if role(k) == "AXSlider"), None)
        ro = next((k for k in kids if role(k) == "AXGroup"), None)
        if lab and sl is not None:
            out[str(lab).rstrip(":")] = (cell, sl, ro)
    return out


def survey_editor(win):
    sliders = find_all(win, lambda e: role(e) == "AXSlider", maxd=14)
    labelled = [s for s in sliders if desc(s) or title(s)]
    print(f"  editor view: sliders={len(sliders)} labelled={len(labelled)}")
    return labelled


def main():
    names = sys.argv[1:] or list(TARGETS)
    banner("T7 set parameter")
    app = app_element(); bring_logic_front(); mw = main_window(app)
    base = wait_for_settle(app)
    select_track(mw, "Audio 1")
    for name in names:
        print(f"\n--- {name} ---")
        got = open_via_search(app, mw, "Audio 1", name)
        win, _ = wait_until(lambda: plugin_win(app, base), timeout=4.0); time.sleep(0.8)
        if got is None or win is None:
            result(f"{name}: window", False, f"loaded={got!r}"); continue
        ed_desc, ed_target, row_label, delta = TARGETS.get(name, (None, None, None, None))
        labelled = survey_editor(win)
        # --- editor-view mechanism (only when the slider is labelled)
        el = next((s for s in labelled if ed_desc and ed_desc.lower() in (desc(s) or title(s) or "").lower()), None)
        if el is not None:
            raw0 = value(el)
            ok, how = set_via_text_field(app, el, ed_target)
            fresh = lambda: next((s for s in find_all(plugin_win(app, base), lambda e: role(e) == "AXSlider", maxd=14)
                                  if ed_desc.lower() in ((desc(s) or title(s) or "").lower())), None)
            changed, dt = wait_until(lambda: (value(fresh()) != raw0) or None, timeout=3.0)
            result(f"{name}: editor {ed_desc} -> {ed_target}", ok and bool(changed), f"{how}; raw {raw0!r}->{value(fresh())!r} ({dt:.2f}s)")
            ax_set(fresh(), AS.kAXValueAttribute, raw0); time.sleep(0.3)
        else:
            result(f"{name}: editor-view named slider", None, f"not available ({ed_desc!r})")
        # --- Controls-view mechanism (universal)
        sw = set_view(app, plugin_win(app, base), "Controls"); time.sleep(0.4)
        r = rows(plugin_win(app, base))
        if not sw or row_label not in r:
            result(f"{name}: controls view", False, f"switched={sw}; rows={list(r)[:8]}"); 
        else:
            cell, sl, ro = r[row_label]; raw0 = value(sl); ro0 = value(ro)
            code = ax_set(sl, AS.kAXValueAttribute, float(raw0) + delta)
            got2, dt = wait_until(lambda: (value(rows(plugin_win(app, base))[row_label][1]) != raw0) or None, timeout=3.0)
            _, sl2, ro2 = rows(plugin_win(app, base))[row_label]
            result(f"{name}: controls {row_label} raw {raw0!r}+{delta}", bool(got2) and value(sl2) == float(raw0) + delta,
                   f"ax_set code={code}; raw {raw0!r}->{value(sl2)!r}; readout {ro0!r}->{value(ro2)!r} ({dt:.2f}s); {len(r)} rows addressable by label")
            screenshot(f"t7_{name.lower().replace(' ', '_')}_controls", window_title=title(plugin_win(app, base)))
            ax_set(sl2, AS.kAXValueAttribute, float(raw0)); time.sleep(0.3)
            set_view(app, plugin_win(app, base), "Editor" if name != "ValhallaSupermassive" else name)
        close_plugin_windows(app, base)
        result(f"    remove {got!r}", remove_plugin(app, mw, "Audio 1", got), "via slot list > No Plug-in")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
