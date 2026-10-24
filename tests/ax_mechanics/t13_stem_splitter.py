"""T13 — the context_menu + checks steps on Stem Splitter, through the real handlers.
Needs one audio region (scrolled into view or not). Opens the sheet three ways, ticks a
subset, reads it back, then presses Cancel (the sheet still keeps the ticks): Apply is never pressed, the project is untouched."""
import time

from core import ax
from core.automation.logic_focus import activate_logic
from core.automation.runner import run_steps
from core.automation.wire import wire_to_steps

OPEN = {"context_menu": ["Stem Splitter…"], "on": "region", "or": ["Processing", "Stem Splitter…"],
        "opens": "Stem Splitter"}
STEMS = ("Vocals", "Drums", "Bass", "Guitar", "Piano", "Other")


def cancel(mw):
    sh = ax.sheet_titled(mw, "Stem Splitter")
    if sh is not None:
        ax.ax_press(ax.find_anywhere(sh, desc_="Cancel", role_="AXButton"))
        ax.wait_until(lambda: ax.sheet_titled(mw, "Stem Splitter") is None, timeout=2.0)


def run(name, wire, want=None):
    mw = ax.main_window(ax.app_element())
    t0 = time.monotonic()
    try:
        run_steps(wire_to_steps(wire), log=print)
        sh = ax.sheet_titled(mw, "Stem Splitter")
        got = {n: bool(ax.value(c)) for n, c in ax.sheet_checkboxes(sh).items() if n in STEMS} if sh else None
        ok = sh is not None and (want is None or got == want)
        print(f"RESULT {name}: {'PASS' if ok else 'FAIL'} ({time.monotonic() - t0:.2f}s) {got}")
    except Exception as exc:
        print(f"RESULT {name}: FAIL {type(exc).__name__}: {exc}")
    finally:
        cancel(mw)
        time.sleep(0.5)


if __name__ == "__main__":
    activate_logic()
    time.sleep(0.5)
    run("open only", [OPEN])
    vd = {n: n in ("Vocals", "Drums") for n in STEMS}
    run("vocals + drums", [OPEN, {"checks": vd, "sheet": "Stem Splitter"}], vd)
    run("Processing fallback", [{**OPEN, "context_menu": ["No Such Item…"]}, {"checks": vd, "sheet": "Stem Splitter"}], vd)
    # the sheet keeps its ticks even after Cancel: end on all six, Logic's default
    every = {n: True for n in STEMS}
    run("all six", [OPEN, {"checks": every, "sheet": "Stem Splitter"}], every)
