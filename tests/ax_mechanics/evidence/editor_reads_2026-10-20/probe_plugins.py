"""Probe every open plug-in window in editor view: where knob names come from (AXDescription,
AXHelp, none), whether the editor's readout is a real value or knob travel, and whether hovering
a knob exposes its value through AX. Moves the mouse, puts it back; changes nothing."""
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


def text_values(win):
    return [(e, ax.value(e)) for e in ax.find_all(win, lambda e: ax.role(e) in ("AXTextField", "AXStaticText"), maxd=14)]


activate_logic()
wait_logic_on_screen(3.0)
app = ax.app_element()
home = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
try:
    for win in ax.app_windows(app):
        plugin = ax.window_plugin_name(win)
        if not plugin:
            continue
        print(f"\n### {plugin} on {ax.title(win)!r} (view {ax.current_view(win)!r})")
        sliders = [e for e in ax.find_all(win, lambda e: ax.role(e) == "AXSlider", maxd=14)
                   if ax.value(e) not in (None, "")]
        by_desc = [e for e in sliders if ax.desc(e)]
        by_help = [e for e in sliders if not ax.desc(e) and _help_name(ax.ax_get(e, "AXHelp"))]
        print(f"  sliders {len(sliders)}: named by desc {len(by_desc)}, by help {len(by_help)}, "
              f"unnamed {len(sliders) - len(by_desc) - len(by_help)}")
        for e in sliders[:6]:
            name = ax.desc(e) or _help_name(ax.ax_get(e, "AXHelp"))
            shown = ax.ax_get(e, "AXValueDescription")
            travel = ax.is_knob_travel(ax.value(e), ax.ax_get(e, "AXMinValue"), ax.ax_get(e, "AXMaxValue"), shown)
            print(f"    {str(name):22} raw={ax.value(e)!s:8} shown={shown!r:14} {'TRAVEL' if travel else 'real' if shown else '-'}")
        target = (by_help or by_desc or sliders or [None])[0]
        if plugin == "Compressor":
            target = next((e for e in by_desc if ax.desc(e) == "Threshold"), target)
        c = ax.center(target) if target is not None else None
        if c is None:
            print("  hover: no slider to try")
            continue
        ax.raise_window(win)
        time.sleep(0.3)
        move((c[0] + 400, c[1] + 400)); time.sleep(0.4)
        before = [v for _, v in text_values(win)]   # by position: AX wrappers are new objects each read
        t0 = time.monotonic(); move(c); hit = None
        while time.monotonic() - t0 < 1.2 and hit is None:
            time.sleep(0.1)
            now = text_values(win)
            if len(now) != len(before):
                hit = (f"{len(before)} fields", f"{len(now)} fields", "count changed"); break
            for i, (e, v) in enumerate(now):
                if before[i] != v:
                    hit = (before[i], v, str(ax.ax_get(e, "AXHelp"))[:30]); break
        name = ax.desc(target) or _help_name(ax.ax_get(target, "AXHelp"))
        print(f"  hover {name!r}: " + (f"{hit[0]!r} -> {hit[1]!r} after {time.monotonic() - t0:.2f}s (field help {hit[2]!r})" if hit else "no AX text change in 1.2s"))
finally:
    move(home)
