"""Read and type plug-in values off the editor's face by OCR, for plug-ins whose Controls view
gives only 0-1 positions (Valhalla 'Mix 0.5' for 50.0 %).

Each AX slider anchors one knob (third-party editors expose them, unnamed and unread). Its
name is the OCR'd label above it (else left of it, on its row) in a crop around it; its value
is the number+unit line just under it in a whole-window OCR. A write double-clicks that value
and types into the text box the plug-in opens, only when AX reports one focused.
"""
from __future__ import annotations

import math
import re
import time

import ApplicationServices as AS

from core import ax
from core.automation.errors import StepAbort
from core.capture.ocr_vision import ocr_lines
from core.capture.window_capture import capture_one_bestres, find_all_logic_pro_windows
from core.events.keyboard import press

_UNIT = r"(?:dB|Hz|kHz|ms|s|%|:1|°|Q|oct)"
_UNIT_ONLY = re.compile(rf"^\s*{_UNIT}\s*$", re.I)
_VALUE = re.compile(rf"^\s*[-+−]?\d[\d.,]*\s*k?{_UNIT}?\s*$", re.I)
_TEXT_BOX_ROLES = ("AXTextField", "AXTextArea")

UP, SIDE, LEFT = 40, 40, 160   # pt of context around a knob for its label crop
BELOW = 40                      # pt under a knob where its value line can sit
SETTLE_S = 0.35
VERIFY_S = 2.0


def is_label(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]{2}", text)) and not _VALUE.match(text) and not _UNIT_ONLY.match(text)


def is_value(text: str) -> bool:
    return bool(_VALUE.match(text))


def _mid(f):
    return f[0] + f[2] / 2, f[1] + f[3] / 2


def pick_label(knob: tuple, lines: list[tuple]) -> str | None:
    """The label for a knob at frame (x, y, w, h) among (text, frame) lines in screen points:
    the closest label line above it, else the nearest one to its left on the same row."""
    kx, ky = _mid(knob)
    top, left = knob[1], knob[0]
    labels = [(t, _mid(f)) for t, f in lines if is_label(t)]
    above = [(t, c) for t, c in labels if top - UP <= c[1] < top and abs(c[0] - kx) <= knob[2] / 2 + SIDE]
    if above:
        return min(above, key=lambda tc: (top - tc[1][1]) + abs(tc[1][0] - kx))[0]
    row = [(t, c) for t, c in labels if left - LEFT <= c[0] < left and abs(c[1] - ky) < knob[3]]
    return max(row, key=lambda tc: tc[1][0])[0] if row else None


def pick_value(knob: tuple, lines: list[tuple]) -> tuple[str, tuple] | None:
    """(text, centre) of the value line for a knob: on it or just under it, centred on it."""
    kx, ky = _mid(knob)
    bottom = knob[1] + knob[3]
    vals = [(t, _mid(f)) for t, f in lines if is_value(t)]
    near = [(t, c) for t, c in vals if ky - 2 <= c[1] <= bottom + BELOW and abs(c[0] - kx) <= knob[2] / 2 + 20]
    return min(near, key=lambda tc: abs(tc[1][0] - kx) + (tc[1][1] - ky)) if near else None


def _quartz_window(win) -> dict | None:
    """The Quartz window-info dict for an AX window (same centre)."""
    c = ax.center(win)
    best = None
    try:
        candidates = find_all_logic_pro_windows()
    except RuntimeError:
        return None
    for w in candidates:
        b = w["kCGWindowBounds"]
        d = math.dist(c, (b["X"] + b["Width"] / 2, b["Y"] + b["Height"] / 2))
        if best is None or d < best[0]:
            best = (d, w)
    return best[1] if best and best[0] < 20 else None


def _screen_lines(img, bounds: dict) -> list[tuple]:
    """OCR `img` (a capture of `bounds`, in points) into (text, (x, y, w, h)) screen lines."""
    sx, sy = img.size[0] / bounds["Width"], img.size[1] / bounds["Height"]
    return [(ln["text"], (bounds["X"] + ln["left"] / sx, bounds["Y"] + ln["top"] / sy, ln["width"] / sx, ln["height"] / sy))
            for ln in ocr_lines(img)]


def _crop_lines(img, bounds: dict, knob: tuple) -> list[tuple]:
    """OCR just the area around a knob: whole-window OCR can merge or drop small labels
    (Tape Delay's "LFO Rate", 10-20), a crop reads them."""
    sx = img.size[0] / bounds["Width"]
    x0, y0 = max(0.0, knob[0] - LEFT - bounds["X"]), max(0.0, knob[1] - UP - bounds["Y"])
    x1 = min(bounds["Width"], knob[0] + knob[2] + SIDE - bounds["X"])
    y1 = min(bounds["Height"], knob[1] + knob[3] - bounds["Y"])
    if x1 <= x0 or y1 <= y0:
        return []
    sub = img.crop((int(x0 * sx), int(y0 * sx), int(x1 * sx), int(y1 * sx)))
    return _screen_lines(sub, {"X": bounds["X"] + int(x0 * sx) / sx, "Y": bounds["Y"] + int(y0 * sx) / sx,
                               "Width": sub.size[0] / sx, "Height": sub.size[1] / sx})


def ocr_knobs(win) -> tuple[list[dict], str | None]:
    """([{name, value, point}], None), or ([], why) when nothing could be read. `point` is the
    value's centre on screen, where a write double-clicks."""
    anchors = [f for f in (ax.frame(e) for e in ax.find_all(win, lambda e: ax.role(e) == "AXSlider", maxd=14))
               if f is not None]
    if not anchors:
        return [], "its editor exposes no knobs to read"
    qw = _quartz_window(win)
    img = capture_one_bestres(qw) if qw else None
    if img is None:
        return [], "its window couldn't be captured"
    bounds = qw["kCGWindowBounds"]
    lines = _screen_lines(img, bounds)
    out, seen = [], set()
    for f in anchors:
        val = pick_value(f, lines)
        name = pick_label(f, _crop_lines(img, bounds, f)) if val else None
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append({"name": name, "value": val[0], "point": val[1]})
    return (out, None) if out else ([], "its editor's labels and values couldn't be read")


def find_knob(win, param: str) -> dict | None:
    knobs, _ = ocr_knobs(win)
    by_name = {k["name"]: k for k in knobs}
    k = ax.match_param(by_name, param)
    return by_name[k] if k else None


def type_value(app, win, knob: dict, text: str) -> str:
    """Double-click the knob's value, type `text` into the text box it opens, Return. Returns
    the readout after; raises StepAbort when no text box opens or the value doesn't change."""
    ax.double_click_at(*knob["point"])
    time.sleep(SETTLE_S)
    f = ax.focused(app)
    if ax.role(f) not in _TEXT_BOX_ROLES:
        # Nothing to type into: keystrokes would reach Logic as key commands.
        press("Escape")
        raise StepAbort(f"double-clicking {knob['name']}'s value didn't open a text box")
    ax.ax_set(f, AS.kAXValueAttribute, str(text))
    press("Return")
    got, _ = ax.wait_until(lambda: (lambda k: k if k and k["value"] != knob["value"] else None)(find_knob(win, knob["name"])),
                           timeout=VERIFY_S, poll=0.2)
    if got is None:
        raise StepAbort(f"typed {text} into {knob['name']} but it still shows {knob['value']}")
    return got["value"]
