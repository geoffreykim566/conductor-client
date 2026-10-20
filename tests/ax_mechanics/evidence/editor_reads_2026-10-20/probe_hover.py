"""Probe: does hovering a Compressor knob (or its name label) expose the value through AX?
Moves the mouse onto each target, waits, diffs every text-ish AX value in the window, then
puts the mouse back. Changes nothing in the project."""
import sys
import time

import Quartz

sys.path.insert(0, "/Users/geoffreykim/Desktop/conductor/client")
from core import ax  # noqa: E402
from core.automation.logic_focus import activate_logic, wait_logic_on_screen  # noqa: E402
from core.ax.mouse import _post_mouse  # noqa: E402

TEXT_ROLES = {"AXTextField", "AXStaticText", "AXSlider", "AXButton"}


def texts(win):
    out = {}
    for i, e in enumerate(ax.find_all(win, lambda e: ax.role(e) in TEXT_ROLES, maxd=14)):
        key = (i, ax.role(e), ax.desc(e) or ax.ax_get(e, "AXHelp") and str(ax.ax_get(e, "AXHelp"))[:25])
        out[key] = (ax.value(e), ax.ax_get(e, "AXValueDescription"), ax.title(e))
    return out


def move(p):
    _post_mouse(Quartz.kCGEventMouseMoved, p)


activate_logic()
wait_logic_on_screen(3.0)
app = ax.app_element()
win = ax.plugin_window_for(app, "Compressor")
if win is None:
    sys.exit("Compressor window isn't open")
ax.raise_window(win)
home = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
_, knob = ax.editor_labelled_slider(win, "Threshold")
label = next((e for e in ax.find_all(win, lambda e: ax.role(e) == "AXTextField" and ax.value(e) == "THRESHOLD", maxd=14)), None)
targets = [("knob", knob), ("name label", label)]
try:
    for name, el in targets:
        c = ax.center(el) if el is not None else None
        print(f"\n== hover {name} at {c}")
        if c is None:
            continue
        move((c[0] + 300, c[1] + 300)); time.sleep(0.4)
        before = texts(win)
        t0 = time.monotonic(); move(c)
        changed = {}
        while time.monotonic() - t0 < 1.5 and not changed:
            time.sleep(0.1)
            after = texts(win)
            changed = {k: (before.get(k), v) for k, v in after.items() if before.get(k) != v}
        print(f"   {len(changed)} AX change(s) after {time.monotonic() - t0:.2f}s")
        for k, (a, b) in list(changed.items())[:10]:
            print(f"   {k}: {a} -> {b}")
        new_windows = [(ax.title(w), ax.role(w)) for w in ax.app_windows(app)]
        print("   windows:", new_windows)
finally:
    move(home)
