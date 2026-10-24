"""The `checks` step: tick and untick named checkboxes on the sheet the previous step opened."""
from __future__ import annotations

from core import ax
from core.automation.errors import StepAbort
from core.events.stop import check_stop


def run_checks(step: dict, log, stop_event=None) -> None:
    """Sets the boxes only. It never presses the sheet's Apply/OK: that's the user's
    call, and until then nothing in the project has changed, so nothing is ledgered."""
    want = step["value"]
    log("  checks: " + ", ".join(f"{n} {'on' if on else 'off'}" for n, on in want.items()))
    check_stop(stop_event)
    mw = ax.main_window(ax.app_element())
    sheet = (ax.sheet_titled(mw, step["sheet"]) if step.get("sheet") else ax.front_sheet(mw)) if mw is not None else None
    if sheet is None:
        raise StepAbort(f"the {step.get('sheet') or 'dialog'} sheet isn't open")
    try:
        pressed = ax.set_checks(sheet, want)
    except ax.AxError as exc:
        raise StepAbort(str(exc)) from exc
    log(f"    pressed {', '.join(pressed)}" if pressed else "    already set")
