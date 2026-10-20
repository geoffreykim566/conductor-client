"""Probe: OCR a small crop around each editor knob instead of the whole window. The crop spans the
knob's AX frame plus a band above it (label) and to its left (same-row labels, e.g. Tape Delay's
Smoothing); the label is the text line closest above, else closest left. Read-only."""
import re
import sys
import time

sys.path.insert(0, "/Users/geoffreykim/Desktop/conductor/client")
from core import ax  # noqa: E402
from core.capture.window_capture import capture_one_bestres  # noqa: E402
from probe_ocr_lines import UNIT_ONLY, VALUE, quartz_for, ocr_lines  # noqa: E402

UP, SIDE, LEFT = 40, 40, 160   # points of context around the knob's frame


def frame(e):
    p, s = ax.ax_get(e, "AXPosition"), ax.ax_get(e, "AXSize")
    return ax.ax_point(p) if hasattr(ax, "ax_point") else None, s


def crop_label(img, qw, e):
    b = qw["kCGWindowBounds"]
    c = ax.center(e)
    sz = ax.ax_get(e, "AXSize")
    w, h = (float(x) for x in re.findall(r"[wh]:([\d.]+)", str(sz)))
    sx = img.size[0] / b["Width"]
    x0, x1 = c[0] - w / 2 - LEFT, c[0] + w / 2 + SIDE
    y0, y1 = c[1] - h / 2 - UP, c[1] + h / 2
    box = [max(0, (x0 - b["X"]) * sx), max(0, (y0 - b["Y"]) * sx), min(img.size[0], (x1 - b["X"]) * sx), min(img.size[1], (y1 - b["Y"]) * sx)]
    sub = img.crop(tuple(int(v) for v in box))
    fake = {"kCGWindowBounds": {"X": b["X"] + box[0] / sx, "Y": b["Y"] + box[1] / sx, "Width": sub.size[0] / sx, "Height": sub.size[1] / sx}}
    lines = ocr_lines(sub, fake)
    labels = [t for t in lines if not VALUE.match(t[0]) and not UNIT_ONLY.match(t[0]) and re.search(r"[A-Za-z]{2}", t[0])]
    top = c[1] - h / 2
    above = [t for t in labels if t[1][1] < top and abs(t[1][0] - c[0]) < w / 2 + SIDE]
    if above:
        return min(above, key=lambda t: (top - t[1][1]) + abs(t[1][0] - c[0]))[0], lines
    left = [t for t in labels if t[1][0] < c[0] - w / 2 and abs(t[1][1] - c[1]) < h]
    return (max(left, key=lambda t: t[1][0])[0] if left else None), lines


app = ax.app_element()
for win in ax.app_windows(app):
    plugin = ax.window_plugin_name(win)
    if not plugin or ax.current_view(win) == "Controls":
        continue
    qw = quartz_for(win)
    img = capture_one_bestres(qw)
    sliders = [e for e in ax.find_all(win, lambda e: ax.role(e) == "AXSlider", maxd=14) if ax.value(e) not in (None, "")]
    t0 = time.monotonic()
    print(f"\n### {plugin}: {len(sliders)} knobs")
    for e in sliders:
        name, lines = crop_label(img, qw, e)
        print(f"   ax-shown={ax.ax_get(e, 'AXValueDescription')!r:12} -> {name!r:20}  crop: {' | '.join(t[0] for t in lines)}")
    print(f"   {time.monotonic() - t0:.2f}s for {len(sliders)} crops")
