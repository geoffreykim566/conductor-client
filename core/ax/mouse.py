"""Tagged synthetic clicks for controls whose AX actions are no-ops."""
from __future__ import annotations

import time

import Quartz

from core.ax.primitives import AxError, ax_press, center, wait_until
from core.events.tag import tag_synthetic


def _post_mouse(kind, point, click_state=None):
    ev = Quartz.CGEventCreateMouseEvent(None, kind, point, Quartz.kCGMouseButtonLeft)
    if click_state is not None:
        Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, click_state)
    tag_synthetic(ev)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def click_at(x, y):
    p = (x, y)
    _post_mouse(Quartz.kCGEventMouseMoved, p)
    time.sleep(0.03)
    _post_mouse(Quartz.kCGEventLeftMouseDown, p, 1)
    _post_mouse(Quartz.kCGEventLeftMouseUp, p, 1)


def double_click_at(x, y):
    p = (x, y)
    _post_mouse(Quartz.kCGEventMouseMoved, p)
    time.sleep(0.03)
    for n in (1, 2):
        _post_mouse(Quartz.kCGEventLeftMouseDown, p, n)
        _post_mouse(Quartz.kCGEventLeftMouseUp, p, n)


def press_or_click(el, changed, timeout=1.5) -> str:
    """AXPress, then fall back to a real click if `changed()` stays false.
    Returns which mechanism took effect ('press' / 'click'); raises if neither."""
    code = ax_press(el)
    got, _ = wait_until(changed, timeout=timeout)
    if got:
        return "press"
    c = center(el)
    if c is None:
        raise AxError(f"AXPress (code {code}) changed nothing and the element has no position")
    click_at(*c)
    got, _ = wait_until(changed, timeout=timeout)
    if not got:
        raise AxError(f"neither AXPress (code {code}) nor a click changed the target")
    return "click"
