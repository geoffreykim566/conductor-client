"""Read and write plugin parameters through the plugin window's Controls view.

Each parameter is an AXCell row {AXStaticText 'Label:', AXGroup readout,
AXSlider | AXCheckBox | AXPopUpButton}; a direct AXValue write on the slider
lands exactly, on every plugin tested including third-party ones.
"""
from __future__ import annotations

import difflib
import re
import time

import ApplicationServices as AS

from core.ax.menus import dismiss_menus, open_menu_of
from core.ax.mouse import press_or_click
from core.ax.primitives import AxError, ax_get, ax_press, ax_set, children, desc, norm, role, title, value, wait_until
from core.ax.search import find_all


_ROW_ROLE = "AXCell"


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


ON = ("on", "true", "1", "yes", "enable", "enabled")
OFF = ("off", "false", "0", "no", "disable", "disabled", "bypass")


def write_param_bool(win, label: str, target) -> dict:
    """On/off rows: AXPress the checkbox (click fallback) until value matches."""
    rows = param_rows(win)
    k = match_param(rows, label)
    if k is None:
        raise AxError(f"parameter {label!r} not found; available: {list(rows)[:30]}")
    _, cb, _ = rows[k]
    if role(cb) != "AXCheckBox":
        raise AxError(f"{k!r} is not an on/off control")
    want = 1 if str(target).strip().lower() in ON else 0
    if int(value(cb) or 0) == want:
        return {"label": k, "raw": value(cb), "readout": "on" if want else "off"}
    press_or_click(cb, lambda: int(value(cb) or 0) == want)
    return {"label": k, "raw": value(cb), "readout": "on" if want else "off"}


def match_param(rows: dict, wanted: str) -> str | None:
    """Exact, then case/space-insensitive, then fuzzy label match."""
    if wanted in rows:
        return wanted
    n = norm(wanted)
    for k in rows:
        if norm(k) == n:
            return k
    for k in rows:
        if n in norm(k) or norm(k) in n:
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


def num(text) -> float | None:
    """First number in a readout like '-18.0 dB', '61 %', '0.5', '1500 Hz'."""
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
    d0 = num(cur["readout"])
    if d0 is None:
        raise AxError(f"readout for {k!r} is not numeric: {cur['readout']!r}")
    if abs(d0 - target) < 1e-6:
        return cur
    lo, hi = slider_range(sl)
    if lo is None or hi is None:
        raise AxError(f"{k!r} exposes no AXMinValue/AXMaxValue")
    lo_d = num(write_param_raw(win, k, lo)["readout"])
    hi_d = num(write_param_raw(win, k, hi)["readout"])
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
        d = num(got["readout"])
        if d is None:
            break
        if best is None or abs(d - target) < abs(num(best["readout"]) - target):
            best = got
        if abs(d - target) < 1e-6 or b - a <= 1:
            break
        if (d < target) == ascending:
            a = mid
        else:
            b = mid
    if best is not None and num(best["readout"]) != num(read_param(win, k)["readout"]):
        best = write_param_raw(win, k, float(best["raw"]))
    return best or read_param(win, k)
