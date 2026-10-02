"""Bring Logic Pro to the front, and refuse to post input unless it is there."""
import time

import Quartz

from config import LOGIC_PRO_APP_NAMES
from core.automation.errors import StepAbort
from core.capture.window_capture import find_all_logic_pro_windows


def frontmost_owner() -> str:
    try:
        from AppKit import NSWorkspace
        from Foundation import NSDate, NSRunLoop
        # NSWorkspace state only refreshes as the run loop runs, and a
        # headless script never pumps it — without this the answer stays
        # frozen at whatever was frontmost when the process launched (i.e.
        # always the terminal, even with Logic visibly in front).
        NSRunLoop.currentRunLoop().runUntilDate_(
            NSDate.dateWithTimeIntervalSinceNow_(0.05))
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return str(app.localizedName()) if app else ""
    except Exception:
        # Fallback: frontmost layer-0 window in z-order.
        wins = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID) or []
        for w in wins:
            if w.get("kCGWindowLayer") == 0:
                return w.get("kCGWindowOwnerName", "")
        return ""


def activate_logic(timeout: float = 3.0) -> bool:
    """Bring the running Logic Pro to the front; True once it's frontmost.

    Conductor-side activation of an already-running app (NSRunningApplication)
    — not Logic lifecycle automation, so no Automation permission involved.
    """
    try:
        from AppKit import NSWorkspace
    except Exception:
        return False
    apps = NSWorkspace.sharedWorkspace().runningApplications()
    target = next((a for a in apps
                   if str(a.localizedName()) in LOGIC_PRO_APP_NAMES), None)
    if target is None:
        return False
    # NSApplicationActivateIgnoringOtherApps (2): deprecated on 14+, but the
    # plain cooperative request is exactly what gets ignored when another
    # app (the terminal running this script) is active.
    target.activateWithOptions_(2)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if frontmost_owner() in LOGIC_PRO_APP_NAMES:
            return True
        time.sleep(0.1)
    return False


def wait_logic_on_screen(timeout: float = 2.0) -> bool:
    """Whether a Logic window is on screen within `timeout`. activate_logic()
    returns as soon as Logic is the frontmost app, but with Logic on another
    desktop its windows are still sliding in: a capture then finds nothing, a
    toggle pre-check reads that as "not showing" and presses the key, closing
    what was already open."""

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if find_all_logic_pro_windows():
                return True
        except RuntimeError:
            pass
        time.sleep(0.1)
    return False


def require_logic_frontmost() -> None:
    owner = frontmost_owner()
    if owner not in LOGIC_PRO_APP_NAMES:
        raise StepAbort(
            f"Logic Pro is not frontmost (frontmost: {owner!r}) — "
            "refusing to post events")


def logic_display() -> tuple[int, object]:
    """(display_id, CGDisplayBounds) of the display holding Logic's largest
    window — NOT necessarily the main display (multi-monitor setups put the
    menu bar Logic responds to on Logic's own display)."""
    display_id = Quartz.CGMainDisplayID()
    try:
        wins = find_all_logic_pro_windows()
        main_win = max(wins, key=lambda w: (w["kCGWindowBounds"]["Width"]
                                            * w["kCGWindowBounds"]["Height"]))
        b = main_win["kCGWindowBounds"]
        cx, cy = b["X"] + b["Width"] / 2, b["Y"] + b["Height"] / 2
        _err, ids, count = Quartz.CGGetActiveDisplayList(16, None, None)
        for did in (ids or [])[:count]:
            db = Quartz.CGDisplayBounds(did)
            if (db.origin.x <= cx < db.origin.x + db.size.width
                    and db.origin.y <= cy < db.origin.y + db.size.height):
                display_id = did
                break
    except Exception:
        pass
    return display_id, Quartz.CGDisplayBounds(display_id)
