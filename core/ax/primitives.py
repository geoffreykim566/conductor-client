"""AX element primitives: attribute read/write, geometry, polling, name normalizing."""
from __future__ import annotations

import time

import ApplicationServices as AS


CANNOT_COMPLETE = -25204
SETTLE_S = 0.35
VERIFY_TIMEOUT_S = 3.0


class AxError(RuntimeError):
    """An AX action failed its act->verify contract."""


def ax_get(el, attr):
    if el is None:
        return None
    err, v = AS.AXUIElementCopyAttributeValue(el, attr, None)
    return v if err == 0 else None


def ax_press(el) -> int:
    return AS.AXUIElementPerformAction(el, AS.kAXPressAction)


def ax_set(el, attr, value) -> int:
    return AS.AXUIElementSetAttributeValue(el, attr, value)


def role(el):
    return ax_get(el, AS.kAXRoleAttribute)


def title(el):
    return ax_get(el, AS.kAXTitleAttribute)


def desc(el):
    return ax_get(el, AS.kAXDescriptionAttribute)


def value(el):
    return ax_get(el, AS.kAXValueAttribute)


def children(el):
    return list(ax_get(el, AS.kAXChildrenAttribute) or [])


def parent(el):
    return ax_get(el, AS.kAXParentAttribute)


def center(el):
    pos = ax_get(el, AS.kAXPositionAttribute)
    size = ax_get(el, AS.kAXSizeAttribute)
    if pos is None or size is None:
        return None
    ok1, pt = AS.AXValueGetValue(pos, AS.kAXValueCGPointType, None)
    ok2, sz = AS.AXValueGetValue(size, AS.kAXValueCGSizeType, None)
    if not (ok1 and ok2):
        return None
    return (pt.x + sz.width / 2, pt.y + sz.height / 2)


def element_at(x, y):
    sw = AS.AXUIElementCreateSystemWide()
    err, el = AS.AXUIElementCopyElementAtPosition(sw, x, y, None)
    return el if err == 0 else None


def wait_until(pred, timeout=VERIFY_TIMEOUT_S, poll=0.1):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        r = pred()
        if r:
            return r, time.monotonic() - t0
        time.sleep(poll)
    return None, time.monotonic() - t0


def norm(s: str) -> str:
    return (s or "").lower().replace(" ", "").replace("-", "")
