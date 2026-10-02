"""Synthetic left-click at a global screen point."""
import time

import Quartz

from core.events.keyboard import KEY_TAP_S
from core.events.stop import check_stop
from core.events.tag import tag_synthetic


def click_at(x_pt: float, y_pt: float, stop_event=None) -> None:
    """Left-click at global screen-point coords (same top-left-origin space
    as kCGWindowBounds, so window-relative math feeds this directly)."""
    check_stop(stop_event)
    point = (x_pt, y_pt)
    move = Quartz.CGEventCreateMouseEvent(
        None, Quartz.kCGEventMouseMoved, point, Quartz.kCGMouseButtonLeft)
    tag_synthetic(move)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, move)
    time.sleep(0.05)
    for kind in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
        ev = Quartz.CGEventCreateMouseEvent(
            None, kind, point, Quartz.kCGMouseButtonLeft)
        tag_synthetic(ev)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(KEY_TAP_S)
