"""Logic Pro's AX application element and its windows."""
from __future__ import annotations

import time

import ApplicationServices as AS
import Quartz
from AppKit import NSWorkspace

from config import LOGIC_PRO_APP_NAMES
from core.ax.primitives import AxError, ax_get, ax_set, title


def logic_pid():
    for a in NSWorkspace.sharedWorkspace().runningApplications():
        if str(a.localizedName()) in LOGIC_PRO_APP_NAMES:
            return a.processIdentifier()
    return None


def app_element():
    pid = logic_pid()
    if pid is None:
        raise AxError("Logic Pro is not running")
    return AS.AXUIElementCreateApplication(pid)


def app_windows(app):
    return list(ax_get(app, AS.kAXWindowsAttribute) or [])


def window_titles(app) -> set[str]:
    return {title(w) or "" for w in app_windows(app)}


def main_window(app):
    for w in app_windows(app):
        if "Tracks" in (title(w) or ""):
            return w
    return None


def focused(app):
    return ax_get(app, AS.kAXFocusedUIElementAttribute)


def raise_window(w) -> None:
    """Bring a Logic window to the front of Logic's own window stack."""
    try:
        AS.AXUIElementPerformAction(w, AS.kAXRaiseAction)
        ax_set(w, AS.kAXMainAttribute, True)
    except Exception:
        pass


def ensure_on_screen(win) -> None:
    """Move a window so it is fully visible (plugin windows can open with the
    header's View menu off the right edge of the display)."""
    try:
        pos = ax_get(win, AS.kAXPositionAttribute); size = ax_get(win, AS.kAXSizeAttribute)
        ok1, pt = AS.AXValueGetValue(pos, AS.kAXValueCGPointType, None)
        ok2, sz = AS.AXValueGetValue(size, AS.kAXValueCGSizeType, None)
        if not (ok1 and ok2):
            return
        bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
        x = min(max(pt.x, bounds.origin.x), bounds.origin.x + bounds.size.width - sz.width)
        y = min(max(pt.y, bounds.origin.y + 25), bounds.origin.y + bounds.size.height - sz.height)
        if (x, y) != (pt.x, pt.y):
            new = AS.AXValueCreate(AS.kAXValueCGPointType, Quartz.CGPoint(x, y))
            ax_set(win, AS.kAXPositionAttribute, new)
            time.sleep(0.2)
    except Exception:
        pass
