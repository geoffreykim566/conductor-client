"""Probe: write a Valhalla value through its double-click text box. Double-click the AXTextArea
readout, set the focused element's AXValue, Return; re-read. Then the same back to the start value.
Changes DELAY 300 -> 250 ms and back."""
import sys
import time

import ApplicationServices as AS
import Quartz

sys.path.insert(0, "/Users/geoffreykim/Desktop/conductor/client")
from core import ax  # noqa: E402
from core.automation.logic_focus import activate_logic, wait_logic_on_screen  # noqa: E402
from core.ax.app import focused  # noqa: E402
from core.ax.mouse import double_click_at  # noqa: E402
from core.events.keyboard import press  # noqa: E402


def readout(win, start):
    """The text area whose value starts with `start` (the tree rebuilds, so re-find each time)."""
    return next((e for e in ax.find_all(win, lambda e: ax.role(e) == "AXTextArea", maxd=16) if str(ax.value(e)).startswith(start)), None)


def write(app, win, cur, new):
    el = readout(win, cur)
    c = ax.center(el)
    double_click_at(*c); time.sleep(0.5)
    f = focused(app)
    print(f"  focused {ax.role(f)} {ax.value(f)!r}")
    t0 = time.monotonic()
    ax.ax_set(f, AS.kAXValueAttribute, new)
    press("Return")
    got, _ = ax.wait_until(lambda: readout(win, new.split()[0]), timeout=2.0)
    print(f"  {cur!r} -> typed {new!r}: now {ax.value(got) if got else None!r} ({time.monotonic() - t0:.2f}s)")
    return got is not None


activate_logic(); wait_logic_on_screen(3.0)
app = ax.app_element()
win = ax.plugin_window_for(app, "ValhallaSupermassive")
ax.raise_window(win); time.sleep(0.3)
home = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
try:
    ok = write(app, win, "300.0", "250")
    time.sleep(0.5)
    if ok:
        write(app, win, "250", "300")
finally:
    if ax.role(focused(app)) == "AXTextArea":
        press("Escape")
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, home, 0))
print("final:", [ax.value(e) for e in ax.find_all(win, lambda e: ax.role(e) == "AXTextArea", maxd=16)])
