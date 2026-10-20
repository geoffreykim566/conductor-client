"""Probe: hover every Compressor knob and record which AX text field swaps to its value, and how
long it takes. Moves the mouse only (put back after); changes nothing."""
import sys
import time

import Quartz

sys.path.insert(0, "/Users/geoffreykim/Desktop/conductor/client")
from core import ax  # noqa: E402
from core.automation.logic_focus import activate_logic, wait_logic_on_screen  # noqa: E402
from core.ax.mouse import _post_mouse  # noqa: E402
from core.ax.state_capture import _help_name  # noqa: E402


def move(p):
    _post_mouse(Quartz.kCGEventMouseMoved, p)


def texts(win):
    return [ax.value(e) for e in ax.find_all(win, lambda e: ax.role(e) == "AXTextField", maxd=14)]


activate_logic(); wait_logic_on_screen(3.0)
app = ax.app_element()
win = ax.plugin_window_for(app, "Compressor")
if win is None:
    sys.exit("Compressor window isn't open")
ax.raise_window(win); time.sleep(0.3)
home = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
sliders = [e for e in ax.find_all(win, lambda e: ax.role(e) == "AXSlider", maxd=14) if ax.value(e) not in (None, "")]
print(f"{len(sliders)} sliders, view {ax.current_view(win)!r}")
try:
    for e in sliders:
        name = ax.desc(e) or _help_name(ax.ax_get(e, "AXHelp"))
        shown = ax.ax_get(e, "AXValueDescription")
        c = ax.center(e)
        move((c[0], c[1] + 400)); time.sleep(0.35)
        before = texts(win)
        t0 = time.monotonic(); move(c); hit = None
        while time.monotonic() - t0 < 1.2 and hit is None:
            time.sleep(0.05)
            now = texts(win)
            if len(now) == len(before):
                diff = [(a, b) for a, b in zip(before, now) if a != b]
                hit = diff or None
        print(f"  {str(name):18} shown={shown!r:8} -> {hit if hit else 'no change'} "
              f"({time.monotonic() - t0:.2f}s)")
finally:
    move(home)
