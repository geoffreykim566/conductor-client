"""Probe: name each editor knob from Vision's whole OCR lines (not words). Per knob: the nearest
label line above it (letters, not a bare unit) and the nearest value line below it (number + unit
when it has one), compared with the knob's AX name/readout. Read-only: no mouse, no clicks."""
import math
import re
import sys

import Vision

sys.path.insert(0, "/Users/geoffreykim/Desktop/conductor/client")
from core import ax  # noqa: E402
from core.ax.state_capture import _help_name  # noqa: E402
from core.capture.ocr_vision import _cgimage_from_pil  # noqa: E402
from core.capture.window_capture import capture_one_bestres, find_all_logic_pro_windows  # noqa: E402

UNIT = r"(?:dB|Hz|kHz|ms|s|%|:1|°|Q|oct)"
UNIT_ONLY = re.compile(rf"^\s*{UNIT}\s*$", re.I)
VALUE = re.compile(rf"^\s*[-+−]?\d[\d.,]*\s*k?{UNIT}?\s*$", re.I)


def quartz_for(win):
    c = ax.center(win)
    best = None
    for w in find_all_logic_pro_windows():
        b = w["kCGWindowBounds"]
        d = math.dist(c, (b["X"] + b["Width"] / 2, b["Y"] + b["Height"] / 2))
        if best is None or d < best[0]:
            best = (d, w)
    return best[1] if best and best[0] < 20 else None


def ocr_lines(img, qw):
    """[(text, (x, y) screen centre, height_pt)] from Vision's lines."""
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)
    h = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(_cgimage_from_pil(img), None)
    h.performRequests_error_([req], None)
    b = qw["kCGWindowBounds"]
    out = []
    for obs in req.results() or []:
        c = obs.topCandidates_(1)
        if not c:
            continue
        bb = obs.boundingBox()
        x = b["X"] + (bb.origin.x + bb.size.width / 2) * b["Width"]
        y = b["Y"] + (1 - bb.origin.y - bb.size.height / 2) * b["Height"]
        out.append((c[0].string().strip(), (x, y), bb.size.height * b["Height"]))
    return out


def nearest(c, cands, above):
    """Closest line on the chosen side, weighting horizontal offset more (labels sit centred)."""
    side = [t for t in cands if (t[1][1] < c[1]) == above]
    return min(side, key=lambda t: abs(t[1][0] - c[0]) * 2 + abs(t[1][1] - c[1]), default=None)


app = ax.app_element()
for win in ax.app_windows(app):
    plugin = ax.window_plugin_name(win)
    if not plugin or ax.current_view(win) == "Controls":
        continue
    qw = quartz_for(win)
    img = capture_one_bestres(qw) if qw else None
    if img is None:
        continue
    lines = ocr_lines(img, qw)
    labels = [t for t in lines if not VALUE.match(t[0]) and not UNIT_ONLY.match(t[0]) and re.search(r"[A-Za-z]{2}", t[0])]
    values = [t for t in lines if VALUE.match(t[0])]
    sliders = [e for e in ax.find_all(win, lambda e: ax.role(e) == "AXSlider", maxd=14) if ax.value(e) not in (None, "")]
    print(f"\n### {plugin} (view {ax.current_view(win)!r}): {len(lines)} lines, {len(sliders)} knobs")
    print("   lines:", " | ".join(t[0] for t in lines))
    for e in sliders:
        c = ax.center(e)
        if c is None:
            continue
        lab, val = nearest(c, labels, True), nearest(c, values, False)
        sz = ax.ax_get(e, "AXSize")
        print(f"   knob ({c[0]:.0f},{c[1]:.0f}) size={sz.width if hasattr(sz, 'width') else sz!s:>5} "
              f"ax-name={ax.desc(e) or _help_name(ax.ax_get(e, 'AXHelp')) or '-'!r:18} ax-shown={ax.ax_get(e, 'AXValueDescription')!r:12} "
              f"| ocr label {lab[0] if lab else None!r:20} ({abs(lab[1][1] - c[1]) if lab else 0:.0f}pt up) "
              f"value {val[0] if val else None!r} ({abs(val[1][1] - c[1]) if val else 0:.0f}pt down)")
