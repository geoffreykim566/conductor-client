"""Probe: double-click a Valhalla value readout (found by OCR) and see what AX exposes: the focused
element, any new text field, the window's text values. Types nothing; Escape, mouse put back."""
import sys
import time

import Quartz

sys.path.insert(0, "/Users/geoffreykim/Desktop/conductor/client")
from core import ax  # noqa: E402
from core.automation.logic_focus import activate_logic, wait_logic_on_screen  # noqa: E402
from core.ax.app import focused  # noqa: E402
from core.ax.mouse import double_click_at  # noqa: E402
from core.capture.window_capture import capture_one_bestres  # noqa: E402
from core.events.keyboard import press  # noqa: E402
from probe_ocr_lines import quartz_for, ocr_lines  # noqa: E402


def fields(win):
    return [(ax.role(e), ax.desc(e), ax.value(e)) for e in ax.find_all(win, lambda e: ax.role(e) in ("AXTextField", "AXTextArea", "AXStaticText"), maxd=16)]


activate_logic(); wait_logic_on_screen(3.0)
app = ax.app_element()
win = ax.plugin_window_for(app, "ValhallaSupermassive")
ax.raise_window(win); time.sleep(0.3)
qw = quartz_for(win)
lines = ocr_lines(capture_one_bestres(qw), qw)
target = next(t for t in lines if t[0] == "300.0 ms")   # DELAY's readout
home = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
before = fields(win)
f0 = focused(app)
print("target", target[0], "at", target[1])
print("before: focused", ax.role(f0), ax.desc(f0), "| fields", before)
try:
    double_click_at(*target[1]); time.sleep(0.6)
    f = focused(app)
    print("after:  focused", ax.role(f), repr(ax.desc(f)), repr(ax.value(f)), "| fields", fields(win))
    qw = quartz_for(win)
    capture_one_bestres(qw).save("ocr_scale/valhalla_after_dblclick.png")
finally:
    press("Escape"); time.sleep(0.3)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, home, 0))
qw = quartz_for(win)
print("after Escape:", [t[0] for t in ocr_lines(capture_one_bestres(qw), qw) if "ms" in t[0]])
