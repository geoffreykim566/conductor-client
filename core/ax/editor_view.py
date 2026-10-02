"""Set plugin parameters in the plugin's own editor view: typed values and band checkboxes."""
from __future__ import annotations

import time

import ApplicationServices as AS

from core.ax.app import focused
from core.ax.controls_view import match_param
from core.ax.mouse import double_click_at, press_or_click
from core.ax.primitives import SETTLE_S, ax_set, center, desc, role, title, value, wait_until
from core.ax.search import find_all
from core.events.keyboard import press


def editor_labelled_slider(win, label: str):
    """Editor view: a slider whose own description matches `label` (only some
    Apple plugins label these -- Channel EQ does, Compressor mostly doesn't)."""
    sliders = [e for e in find_all(win, lambda e: role(e) == "AXSlider" and (desc(e) or title(e)), maxd=14)]
    names = {(desc(e) or title(e)): e for e in sliders}
    k = match_param(names, label)
    return (k, names[k]) if k else (None, None)


def type_param_value(app, win, label: str, text: str) -> dict | None:
    """Editor view: double-click the labelled slider, type the display value into
    the focused text field, Return. Returns {'label','raw'} or None if this
    plugin has no labelled slider for the parameter."""
    k, el = editor_labelled_slider(win, label)
    if el is None:
        return None
    c = center(el)
    if c is None:
        return None
    raw0 = value(el)
    double_click_at(*c)
    time.sleep(SETTLE_S)
    f = focused(app)
    if f is None or role(f) != "AXTextField":
        print(f"[ax] typed path unavailable for {k!r}: double-click focused {role(f)!r} {desc(f)!r}")
        press("Escape")
        return None
    text_before = value(f)
    ax_set(f, AS.kAXValueAttribute, str(text))
    press("Return")
    _, el2 = editor_labelled_slider(win, k)
    wait_until(lambda: (value(el2) != raw0) or None, timeout=1.5)
    return {"label": k, "raw": value(el2), "raw_before": raw0, "text_before": text_before}


def editor_checkbox(win, label: str):
    """Editor view: a checkbox whose description matches `label` (band enables
    like 'Low Cut', bypass...). Returns (label, element) or (None, None)."""
    boxes = {(desc(e) or title(e)): e for e in find_all(win, lambda e: role(e) == "AXCheckBox" and (desc(e) or title(e)), maxd=14)}
    k = match_param(boxes, label)
    return (k, boxes[k]) if k else (None, None)


def set_editor_checkbox(cb, on: bool) -> bool:
    """Returns True if the value was changed (False if already there)."""
    cur = bool(value(cb))
    if cur == on:
        return False
    press_or_click(cb, lambda: bool(value(cb)) == on)
    return True
