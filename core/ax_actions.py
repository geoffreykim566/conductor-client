"""Accessibility-API toolkit for driving Logic Pro directly (no OCR).

Promoted from tests/ax_mechanics/_ax_common.py after the 2026-09-18 suite
(see tests/ax_mechanics/RESULTS.md). Rules encoded here, all live-verified on
Logic Pro 12.3.1:

  * An AX action's return code is never evidence. Logic gives both false
    success (track Mute/Solo `AXPress` does nothing) and false failure
    (`kAXErrorCannotComplete` while the menu opens anyway). Verify by
    re-reading state after a settle loop; fall back to a real click at the
    element's AX center when nothing changed.
  * Menu drills must check for a terminal sub-choice (Mono / Stereo,
    Stereo / 5.1) after the last hop.
  * Plugin identity = the plugin window's titled editor AXGroup; the
    channel-strip slot label is truncated and width-dependent.
  * Parameter addressing = plugin window -> View "Controls" -> AXCell rows
    {AXStaticText 'Label:', AXGroup readout, AXSlider}; a direct AXValue
    write on that slider lands exactly, on every plugin tested incl.
    third-party.

Synthetic mouse events posted here are tagged like the executor's so the
interrupt tap never mistakes them for real user input.
"""
from __future__ import annotations

import difflib
import time

import ApplicationServices as AS
import Quartz
from AppKit import NSWorkspace

from config import LOGIC_PRO_APP_NAMES

CANNOT_COMPLETE = -25204
SETTLE_S = 0.35
VERIFY_TIMEOUT_S = 3.0
_ROW_ROLE = "AXCell"


class AxError(RuntimeError):
    """An AX action failed its act->verify contract."""


# --- primitives ---------------------------------------------------------------

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


# --- app / windows ------------------------------------------------------------

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


# --- search -------------------------------------------------------------------

def find_child(el, attr, target, role_=None):
    for c in children(el):
        if role_ and role(c) != role_:
            continue
        if ax_get(c, attr) == target:
            return c
    return None


def find_anywhere(el, *, desc_=None, title_=None, role_=None, depth=0, maxd=12):
    if el is None:
        return None
    if (desc_ is not None or title_ is not None) and \
            (desc_ is None or desc(el) == desc_) and (title_ is None or title(el) == title_) and \
            (role_ is None or role(el) == role_):
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
    if el is None:
        return out
    if pred(el):
        out.append(el)
    if depth < maxd:
        for c in children(el):
            find_all(c, pred, depth + 1, maxd, out)
    return out


# --- synthetic mouse (tagged; needed where AX actions are no-ops) -------------

def _post_mouse(kind, point, click_state=None):
    from core.executor import _tag_synthetic
    ev = Quartz.CGEventCreateMouseEvent(None, kind, point, Quartz.kCGMouseButtonLeft)
    if click_state is not None:
        Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, click_state)
    _tag_synthetic(ev)
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


# --- menus ----------------------------------------------------------------------

def current_menu(app, point=None):
    node = focused(app)
    for _ in range(6):
        if node is None:
            break
        if role(node) == "AXMenu":
            return node
        node = parent(node)
    if point:
        el = element_at(*point)
        p = parent(el) if el is not None else None
        if p is not None and role(p) == "AXMenu":
            return p
    return None


def open_menu_of(app, button):
    """AXPress a menu/popup button and return its open AXMenu (children of the
    button, else via focus, else element-at-position), or None."""
    c = center(button)
    ax_press(button)
    time.sleep(SETTLE_S)
    menu = next((k for k in children(button) if role(k) == "AXMenu"), None) or current_menu(app, c)
    if menu is None and c is not None:
        click_at(*c)
        time.sleep(SETTLE_S)
        menu = next((k for k in children(button) if role(k) == "AXMenu"), None) or current_menu(app, c)
    return menu


def drill(menu, path: list[str], prefer_terminal=("Stereo", "Mono")) -> None:
    """AXPress each hop by title. Handles a terminal item that still opens a
    sub-choice (Mono / Mono->Stereo, Stereo / 5.1)."""
    for i, hop in enumerate(path):
        items = children(menu)
        item = next((it for it in items if (title(it) or "").strip() == hop), None) or \
            next((it for it in items if hop.lower() in (title(it) or "").lower()), None)
        if item is None:
            raise AxError(f"menu item {hop!r} not found; items: {[title(it) for it in items][:20]}")
        ax_press(item)
        time.sleep(SETTLE_S)
        last = i == len(path) - 1
        sub, _ = wait_until(lambda: next((c for c in children(item) if role(c) == "AXMenu" and children(c)), None),
                            timeout=0.8 if last else 1.5)
        if not last:
            if sub is None:
                raise AxError(f"submenu for {hop!r} did not populate")
            menu = sub
        elif sub is not None:
            subs = [c for c in children(sub) if title(c)]
            pick = next((c for c in subs if title(c) in prefer_terminal), subs[0] if subs else None)
            if pick is None:
                raise AxError(f"terminal {hop!r} opened an empty submenu")
            ax_press(pick)
            time.sleep(SETTLE_S)


def dismiss_menus(app) -> None:
    from core.executor import press
    for _ in range(3):
        if current_menu(app) is None:
            return
        press("Escape")
        time.sleep(0.2)


# --- channel strip / plugins --------------------------------------------------------

def strip(mw, track_name: str):
    mixer = find_anywhere(mw, desc_="Mixer", role_="AXLayoutArea")
    return find_child(mixer, AS.kAXDescriptionAttribute, track_name, "AXLayoutItem") if mixer else None


def selected_strip(mw):
    """The Inspector shows the selected track's strip first (before 'Stereo Out')."""
    mixer = find_anywhere(mw, desc_="Mixer", role_="AXLayoutArea")
    items = [c for c in children(mixer) if role(c) == "AXLayoutItem"] if mixer else []
    return items[0] if items else None


def _is_slot_group(c):
    return role(c) == "AXGroup" and {"bypass", "open", "list"} <= {desc(k) for k in children(c)}


def fx_slots(strip_el):
    empty = find_child(strip_el, AS.kAXDescriptionAttribute, "audio plug-in", "AXButton") if strip_el else None
    loaded = [c for c in children(strip_el) if _is_slot_group(c)] if strip_el else []
    return empty, loaded


def loaded_names(strip_el) -> list[str]:
    return [desc(g) or "" for g in fx_slots(strip_el)[1]]


def _norm(s: str) -> str:
    return (s or "").lower().replace(" ", "").replace("-", "")


def plugin_window_for(app, name: str, before: set[str] | None = None):
    """Find the open plugin window for `name` (title = track name; identity = the
    titled editor AXGroup or the trailing AXStaticText)."""
    for w in app_windows(app):
        if before is not None and title(w) in before:
            continue
        shown = window_plugin_name(w)
        if shown and (_norm(name) in _norm(shown) or _norm(shown) in _norm(name)):
            return w
    return None


def window_plugin_name(w) -> str | None:
    """Plugin windows are titled after the track. Identity: the header's own
    plugin-name AXStaticText (a DIRECT child of the window, present in both
    Editor and Controls view), else the titled editor AXGroup (Editor view)."""
    direct = [value(c) for c in children(w) if role(c) == "AXStaticText" and value(c)]
    direct = [t for t in direct if t not in ("View:", title(w)) and not str(t).endswith(":")]
    if direct:
        return direct[-1]
    g = next((c for c in children(w) if role(c) == "AXGroup" and title(c)), None)
    return title(g) if g is not None else None


def open_plugin_by_search(app, mw, name: str, stop_check=None) -> tuple[str, object, int]:
    """Search-and-Add-Plug-in on the selected strip: Ctrl+Cmd+P, set the search
    field's AXValue, Return. Returns (slot_label, plugin_window). Verifies by the
    plugin window's own name, never the truncated slot label."""
    from core.executor import press
    s = selected_strip(mw)
    before_w = window_titles(app)
    before_n = loaded_names(s)
    press("Ctrl+Cmd+P")
    f, _ = wait_until(lambda: (lambda x: x if x is not None and role(x) == "AXTextField" else None)(focused(app)), timeout=2.0)
    if f is None:
        raise AxError("Search-and-Add-Plug-in field did not take focus")
    ax_set(f, AS.kAXValueAttribute, name)
    time.sleep(0.5)
    press("Return")
    # count-based: a second instance of an already-loaded plugin has the same label
    got, _ = wait_until(lambda: (lambda n: n if len(n) > len(before_n) else None)(loaded_names(selected_strip(mw))), timeout=5.0)
    if not got:
        dismiss_menus(app)
        raise AxError(f"no plugin loaded for {name!r}")
    new_idx = next((i for i, n in enumerate(got) if i >= len(before_n) or n != before_n[i]), len(got) - 1)
    win, _ = wait_until(lambda: plugin_window_for(app, name, before_w), timeout=4.0)
    if win is None:
        # something loaded but it isn't the requested plugin (recency collision) -- undo it
        remove_plugin(app, mw, got[new_idx], index=new_idx)
        raise AxError(f"search loaded {got[new_idx]!r}, not {name!r}")
    ensure_on_screen(win)
    return got[new_idx], win, new_idx


def loaded_slot(strip_el, name: str, index: int | None = None):
    """The slot group for a loaded plugin, by index if given else by label prefix."""
    groups = fx_slots(strip_el)[1]
    if index is not None and 0 <= index < len(groups):
        return groups[index]
    key = _norm(name)[:6]
    return next((g for g in groups if _norm(desc(g)).startswith(key)), None)


def open_loaded_plugin(app, mw, name: str, index: int | None = None):
    """Open the window of an already-loaded plugin via its slot's 'open' button."""
    g = loaded_slot(selected_strip(mw), name, index)
    if g is None:
        return None
    before_w = window_titles(app)
    win = plugin_window_for(app, name)
    if win is None:
        ax_press(find_child(g, AS.kAXDescriptionAttribute, "open", "AXButton"))
        win, _ = wait_until(lambda: plugin_window_for(app, name, before_w), timeout=4.0)
    if win is not None:
        ensure_on_screen(win)
    return win


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


def remove_plugin(app, mw, slot_label: str, index: int | None = None) -> bool:
    """Open the loaded slot's 'list' menu and choose 'No Plug-in'."""
    s = selected_strip(mw)
    key = _norm(slot_label)[:6]
    g = loaded_slot(s, slot_label, index)
    if g is None:
        return False
    n_before = len(fx_slots(s)[1])
    lst = find_child(g, AS.kAXDescriptionAttribute, "list", "AXButton")
    menu = open_menu_of(app, lst)
    item = next((i for i in children(menu) if (title(i) or "").startswith("No Plug-in")), None) if menu else None
    if item is None:
        dismiss_menus(app)
        return False
    ax_press(item)
    gone, _ = wait_until(lambda: (len(fx_slots(selected_strip(mw))[1]) < n_before) or None, timeout=3.0)
    return bool(gone)


# --- plugin parameters (Controls view) ------------------------------------------------

def set_view(app, win, name: str) -> bool:
    btn = next((c for c in children(win) if role(c) == "AXMenuButton" and desc(c) == "view"), None)
    if btn is None:
        return False
    if (title(btn) or "") == name:
        return True
    menu = open_menu_of(app, btn)
    it = next((i for i in children(menu) if title(i) == name), None) if menu else None
    if it is None:
        dismiss_menus(app)
        return False
    ax_press(it)
    time.sleep(0.8)
    return True


def param_rows(win) -> dict[str, tuple]:
    """Controls view: label -> (cell, control, readout). `control` is the row's
    AXSlider (numeric), AXCheckBox (on/off rows like 'Low Cut On/Off') or
    AXPopUpButton (choice rows); readout is the AXGroup text or None."""
    out = {}
    for cell in find_all(win, lambda e: role(e) == _ROW_ROLE, maxd=14):
        kids = children(cell)
        lab = next((value(k) for k in kids if role(k) == "AXStaticText"), None)
        ctl = next((k for k in kids if role(k) in ("AXSlider", "AXCheckBox", "AXPopUpButton")), None)
        ro = next((k for k in kids if role(k) == "AXGroup"), None)
        if lab and ctl is not None:
            out[str(lab).rstrip(":").strip()] = (cell, ctl, ro)
    return out


_ON = ("on", "true", "1", "yes", "enable", "enabled")
_OFF = ("off", "false", "0", "no", "disable", "disabled", "bypass")


def write_param_bool(win, label: str, target) -> dict:
    """On/off rows: AXPress the checkbox (click fallback) until value matches."""
    rows = param_rows(win)
    k = match_param(rows, label)
    if k is None:
        raise AxError(f"parameter {label!r} not found; available: {list(rows)[:30]}")
    _, cb, _ = rows[k]
    if role(cb) != "AXCheckBox":
        raise AxError(f"{k!r} is not an on/off control")
    want = 1 if str(target).strip().lower() in _ON else 0
    if int(value(cb) or 0) == want:
        return {"label": k, "raw": value(cb), "readout": "on" if want else "off"}
    press_or_click(cb, lambda: int(value(cb) or 0) == want)
    return {"label": k, "raw": value(cb), "readout": "on" if want else "off"}


def match_param(rows: dict, wanted: str) -> str | None:
    """Exact, then case/space-insensitive, then fuzzy label match."""
    if wanted in rows:
        return wanted
    n = _norm(wanted)
    for k in rows:
        if _norm(k) == n:
            return k
    for k in rows:
        if n in _norm(k) or _norm(k) in n:
            return k
    close = difflib.get_close_matches(wanted, list(rows), n=1, cutoff=0.6)
    return close[0] if close else None


def read_param(win, label: str):
    rows = param_rows(win)
    k = match_param(rows, label)
    if k is None:
        return None
    _, ctl, ro = rows[k]
    readout = value(ro) if ro is not None else ("on" if value(ctl) else "off")
    return {"label": k, "raw": value(ctl), "readout": readout, "kind": role(ctl)}


def write_param_raw(win, label: str, raw: float) -> dict:
    rows = param_rows(win)
    k = match_param(rows, label)
    if k is None:
        raise AxError(f"parameter {label!r} not found; available: {list(rows)[:30]}")
    _, sl, _ = rows[k]
    ax_set(sl, AS.kAXValueAttribute, float(raw))
    got, _ = wait_until(lambda: (lambda r: r if r and r["raw"] == float(raw) else None)(read_param(win, k)), timeout=2.0)
    if not got:
        raise AxError(f"write to {k!r} did not take (raw now {read_param(win, k)})")
    return got


def _num(text) -> float | None:
    """First number in a readout like '-18.0 dB', '61 %', '0.5', '1500 Hz'."""
    import re
    if text is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(text).replace(",", ""))
    return float(m.group()) if m else None


def slider_range(sl) -> tuple[float | None, float | None]:
    lo = ax_get(sl, AS.kAXMinValueAttribute)
    hi = ax_get(sl, AS.kAXMaxValueAttribute)
    return (float(lo) if lo is not None else None, float(hi) if hi is not None else None)


def write_param_display(win, label: str, target: float, max_iter: int = 14) -> dict:
    """Set a parameter so its READOUT shows `target` (display units). The raw
    <-> display mapping is per-parameter and often non-linear (frequencies are
    logarithmic), so bisect on raw within the slider's [min, max] against the
    numeric readout. Ends on the nearest reachable value."""
    rows = param_rows(win)
    k = match_param(rows, label)
    if k is None:
        raise AxError(f"parameter {label!r} not found; available: {list(rows)[:30]}")
    _, sl, _ = rows[k]
    cur = read_param(win, k)
    d0 = _num(cur["readout"])
    if d0 is None:
        raise AxError(f"readout for {k!r} is not numeric: {cur['readout']!r}")
    if abs(d0 - target) < 1e-6:
        return cur
    lo, hi = slider_range(sl)
    if lo is None or hi is None:
        raise AxError(f"{k!r} exposes no AXMinValue/AXMaxValue")
    lo_d = _num(write_param_raw(win, k, lo)["readout"])
    hi_d = _num(write_param_raw(win, k, hi)["readout"])
    if lo_d is None or hi_d is None:
        raise AxError(f"{k!r} readout not numeric at range ends")
    ascending = hi_d >= lo_d
    if (ascending and target <= lo_d) or (not ascending and target >= lo_d):
        return write_param_raw(win, k, lo)
    if (ascending and target >= hi_d) or (not ascending and target <= hi_d):
        return write_param_raw(win, k, hi)
    a, b = lo, hi
    best = None
    for _ in range(max_iter):
        mid = round((a + b) / 2)
        got = write_param_raw(win, k, mid)
        d = _num(got["readout"])
        if d is None:
            break
        if best is None or abs(d - target) < abs(_num(best["readout"]) - target):
            best = got
        if abs(d - target) < 1e-6 or b - a <= 1:
            break
        if (d < target) == ascending:
            a = mid
        else:
            b = mid
    if best is not None and _num(best["readout"]) != _num(read_param(win, k)["readout"]):
        best = write_param_raw(win, k, float(best["raw"]))
    return best or read_param(win, k)


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
    from core.executor import press
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
