"""Shared toolkit for the AX execution-mechanics suite.

Lifted from the July 2026 diagnostics (see the archived
`.old-drafts-planning-docs/ax-exploration-log.md`, section "How this session
actually tested things"). Every test in this directory:

  1. brings Logic Pro to the front via `activate_logic()` and then HARD-GATES on
     `_frontmost_owner()` — never trusts the activation call alone;
  2. captures a baseline window set and aborts (never guesses) on unexpected
     state;
  3. re-checks frontmost after every action;
  4. verifies by RE-READING resulting AX state after a settle loop. An action's
     return code is never treated as evidence — Logic gives both false success
     (menu chain reports ok, nothing opens) and false failure
     (`kAXErrorCannotComplete` -25204 while the menu actually opens).

Run from the client-v3 root:  PYTHONUNBUFFERED=1 .venv/bin/python -m tests.ax_mechanics.<test>
"""
from __future__ import annotations

import pathlib
import sys
import time

import ApplicationServices as AS
import Quartz
from AppKit import NSWorkspace

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import LOGIC_PRO_APP_NAMES  # noqa: E402
from core.executor import _frontmost_owner, activate_logic, press  # noqa: E402

CANNOT_COMPLETE = -25204


class AbortRun(Exception):
    pass


# --- primitives --------------------------------------------------------------

def ax_get(el, attr):
    err, v = AS.AXUIElementCopyAttributeValue(el, attr, None)
    return v if err == 0 else None


def ax_attr_names(el):
    err, names = AS.AXUIElementCopyAttributeNames(el, None)
    return list(names) if err == 0 and names else []


def ax_action_names(el):
    err, names = AS.AXUIElementCopyActionNames(el, None)
    return list(names) if err == 0 and names else []


def ax_press(el) -> int:
    """Returns the raw error code (0 = reported ok). Do NOT treat as truth."""
    return AS.AXUIElementPerformAction(el, AS.kAXPressAction)


def ax_action(el, action: str) -> int:
    return AS.AXUIElementPerformAction(el, action)


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


def center(el):
    """Screen-space center of an element, or None."""
    pos = ax_get(el, AS.kAXPositionAttribute)
    size = ax_get(el, AS.kAXSizeAttribute)
    if pos is None or size is None:
        return None
    ok1, pt = AS.AXValueGetValue(pos, AS.kAXValueCGPointType, None)
    ok2, sz = AS.AXValueGetValue(size, AS.kAXValueCGSizeType, None)
    if not (ok1 and ok2):
        return None
    return (pt.x + sz.width / 2, pt.y + sz.height / 2)


# --- app / windows -----------------------------------------------------------

def find_pid():
    for a in NSWorkspace.sharedWorkspace().runningApplications():
        if str(a.localizedName()) in LOGIC_PRO_APP_NAMES:
            return a.processIdentifier()
    return None


def app_element():
    pid = find_pid()
    if pid is None:
        raise AbortRun("Logic Pro is not running")
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


def assert_frontmost(context: str):
    owner = _frontmost_owner()
    if owner not in LOGIC_PRO_APP_NAMES:
        raise AbortRun(f"Logic Pro not frontmost at {context!r} — frontmost is {owner!r}")


def bring_logic_front():
    """activate_logic() + hard gate. Falls back to asking the human."""
    try:
        activate_logic()
    except Exception as e:  # noqa: BLE001
        print(f"  activate_logic() raised {e!r}; waiting 3s for a manual click into Logic")
        time.sleep(3)
    time.sleep(0.4)
    assert_frontmost("startup")


def wait_for_settle(app, timeout=1.5, poll=0.1) -> set[str]:
    """Wait until two consecutive window-title reads agree."""
    last = None
    t0 = time.time()
    while time.time() - t0 < timeout:
        cur = window_titles(app)
        if cur == last:
            return cur
        last = cur
        time.sleep(poll)
    return window_titles(app)


def wait_until(pred, timeout=3.0, poll=0.1):
    """Poll `pred()` until truthy; returns (result, elapsed_s) or (None, elapsed)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = pred()
        if r:
            return r, time.time() - t0
        time.sleep(poll)
    return None, time.time() - t0


# --- search ------------------------------------------------------------------

def find_child(el, attr, target, role_=None):
    for c in children(el):
        if role_ and role(c) != role_:
            continue
        if ax_get(c, attr) == target:
            return c
    return None


def find_anywhere(el, *, desc_=None, title_=None, role_=None, depth=0, maxd=12):
    d = desc(el) if desc_ is not None else None
    t = title(el) if title_ is not None else None
    if (desc_ is None or d == desc_) and (title_ is None or t == title_) \
            and (role_ is None or role(el) == role_) and (desc_ is not None or title_ is not None):
        return el
    if depth >= maxd:
        return None
    for c in children(el):
        r = find_anywhere(c, desc_=desc_, title_=title_, role_=role_, depth=depth + 1, maxd=maxd)
        if r is not None:
            return r
    return None


def find_all(el, pred, depth=0, maxd=12, out=None):
    out = [] if out is None else out
    if pred(el):
        out.append(el)
    if depth < maxd:
        for c in children(el):
            find_all(c, pred, depth + 1, maxd, out)
    return out


def describe(el, depth=0, max_depth=3, max_children=25, indent=""):
    r, t, d, v = role(el), title(el), desc(el), value(el)
    bits = [str(r)]
    if t:
        bits.append(f"title={t!r}")
    if d and d != t:
        bits.append(f"desc={d!r}")
    if v is not None and not isinstance(v, (AS.AXUIElementRef if hasattr(AS, 'AXUIElementRef') else tuple)):
        s = repr(v)
        bits.append(f"value={s[:60]}")
    print(f"{indent}- {' '.join(bits)}")
    if depth >= max_depth:
        return
    for c in children(el)[:max_children]:
        describe(c, depth + 1, max_depth, max_children, indent + "  ")


def element_at(x, y):
    sw = AS.AXUIElementCreateSystemWide()
    err, el = AS.AXUIElementCopyElementAtPosition(sw, x, y, None)
    return el if err == 0 else None


# --- synthetic mouse (real CGEvents; needed for popups + entering edit mode) --

def _post_mouse(kind, point, click_state=None):
    ev = Quartz.CGEventCreateMouseEvent(None, kind, point, Quartz.kCGMouseButtonLeft)
    if click_state is not None:
        Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, click_state)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)


def click_at(x, y):
    p = (x, y)
    _post_mouse(Quartz.kCGEventMouseMoved, p)
    _post_mouse(Quartz.kCGEventLeftMouseDown, p, 1)
    _post_mouse(Quartz.kCGEventLeftMouseUp, p, 1)


def double_click_at(x, y):
    """A REAL double-click: macOS keys on kCGMouseEventClickState, two plain
    clicks are not recognised as a double-click."""
    p = (x, y)
    _post_mouse(Quartz.kCGEventMouseMoved, p)
    for n in (1, 2):
        _post_mouse(Quartz.kCGEventLeftMouseDown, p, n)
        _post_mouse(Quartz.kCGEventLeftMouseUp, p, n)


# --- higher-level helpers ------------------------------------------------------

def set_via_text_field(app, el, text: str, settle=0.35) -> tuple[bool, str]:
    """Double-click a slider/knob/name, set the focused AXTextField's value,
    commit with Return. Returns (committed, focused_desc)."""
    c = center(el)
    if c is None:
        return False, "no position"
    assert_frontmost("before double-click")
    double_click_at(*c)
    time.sleep(settle)
    f = focused(app)
    if f is None or role(f) != "AXTextField":
        return False, f"focused={role(f)!r} {desc(f)!r}"
    err = ax_set(f, AS.kAXValueAttribute, text)
    if err != 0:
        return False, f"AXValue set err={err}"
    assert_frontmost("before Return")
    press("Return")
    time.sleep(settle)
    return True, f"ok via {desc(f)!r}"


def close_window(w) -> bool:
    for c in children(w):
        if ax_get(c, AS.kAXSubroleAttribute) == "AXCloseButton":
            ax_press(c)
            return True
    return False


def banner(name: str):
    print("\n" + "=" * 78 + f"\n{name}\n" + "=" * 78)


def result(name: str, ok: bool | None, evidence: str):
    tag = "PASS" if ok else ("FAIL" if ok is False else "INFO")
    print(f"  [{tag}] {name}: {evidence}")


# --- evidence ------------------------------------------------------------------

EVIDENCE_DIR = pathlib.Path(__file__).resolve().parent / "evidence"


def logic_window_ids() -> list[int]:
    wl = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID)
    out = []
    for w in wl:
        if w.get("kCGWindowOwnerName") in LOGIC_PRO_APP_NAMES and w.get("kCGWindowLayer", 0) in (0, 3, 8, 25, 101):
            b = w.get("kCGWindowBounds", {})
            if b.get("Width", 0) > 200 and b.get("Height", 0) > 100:
                out.append((int(b.get("Width", 0) * b.get("Height", 0)), int(w["kCGWindowNumber"])))
    return [wid for _, wid in sorted(out, reverse=True)]


def screenshot(name: str, window_title: str | None = None) -> str | None:
    """Independent visual evidence. Captures the Logic window whose title contains
    `window_title`, else the largest Logic window."""
    import subprocess
    EVIDENCE_DIR.mkdir(exist_ok=True)
    wid = None
    if window_title:
        wl = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID)
        for w in wl:
            if w.get("kCGWindowOwnerName") in LOGIC_PRO_APP_NAMES and window_title in (w.get("kCGWindowName") or ""):
                wid = int(w["kCGWindowNumber"]); break
    if wid is None:
        ids = logic_window_ids()
        if not ids:
            return None
        wid = ids[0]
    path = EVIDENCE_DIR / f"{name}.png"
    subprocess.run(["screencapture", "-x", "-o", "-l", str(wid), str(path)], check=False)
    return str(path) if path.exists() else None


def track_headers(mw):
    hdr = find_anywhere(mw, desc_="Tracks header", role_="AXGroup")
    return [c for c in children(hdr)] if hdr is not None else []


def track_header(mw, name: str):
    for h in track_headers(mw):
        if f"“{name}”" in (desc(h) or ""):
            return h
    return None
