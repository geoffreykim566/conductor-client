"""Sheets on Logic's main window (Stem Splitter): find one by its heading, read and set its checkboxes."""
from __future__ import annotations

import time

from core.ax.primitives import AxError, ax_press, children, desc, role, value, wait_until
from core.ax.search import find_all, find_anywhere


def sheet_titled(mw, heading: str):
    """The main window's sheet headed `heading` (an AXHeading's description), or None."""
    for c in children(mw):
        if role(c) == "AXSheet" and find_anywhere(c, desc_=heading, role_="AXHeading") is not None:
            return c
    return None


def front_sheet(mw):
    return next((c for c in children(mw) if role(c) == "AXSheet"), None)


def sheet_checkboxes(sheet) -> dict:
    """{name: checkbox element} for the sheet's checkboxes, named by their description."""
    return {desc(c): c for c in find_all(sheet, lambda e: role(e) == "AXCheckBox", maxd=8) if desc(c)}


def checks_to_press(current: dict[str, bool], want: dict[str, bool]) -> list[str]:
    """Pure: the names whose box differs from what's wanted. A wanted name the sheet
    doesn't have raises, so a renamed box stops the step instead of being skipped."""
    missing = [n for n in want if n not in current]
    if missing:
        raise AxError(f"no {', '.join(missing)} checkbox here; it has {', '.join(current)}")
    return [n for n, on in want.items() if current[n] != on]


def set_checks(sheet, want: dict[str, bool]) -> list[str]:
    """Press the boxes that differ from `want`, then read every one back. Returns the
    names pressed; raises AxError if any box doesn't end as wanted."""
    boxes = sheet_checkboxes(sheet)
    pressed = checks_to_press({n: bool(value(c)) for n, c in boxes.items()}, want)
    for n in pressed:
        ax_press(boxes[n])
        time.sleep(0.1)
    ok, _ = wait_until(lambda: all(bool(value(boxes[n])) == want[n] for n in want), timeout=1.5)
    if not ok:
        wrong = [n for n in want if bool(value(boxes[n])) != want[n]]
        raise AxError(f"{', '.join(wrong)} didn't change")
    return pressed
