"""Probe: can OCR of a plug-in's editor name its unnamed AX knobs (and read values AX lacks)?
For each plug-in window: capture it, OCR it, then for every AX slider list the nearest OCR'd
word-like label and number-like value by screen distance. Read-only: no mouse, no clicks."""
import math
import re
import sys

sys.path.insert(0, "/Users/geoffreykim/Desktop/conductor/client")
from core import ax  # noqa: E402
from core.automation.ocr_find import box_center_screen  # noqa: E402
from core.capture.ocr_vision import ocr_words  # noqa: E402
from core.capture.window_capture import capture_one_bestres, find_all_logic_pro_windows  # noqa: E402

NUMBER = re.compile(r"-?\d")


def quartz_for(win):
    c = ax.center(win)
    best = None
    for w in find_all_logic_pro_windows():
        b = w["kCGWindowBounds"]
        d = math.dist(c, (b["X"] + b["Width"] / 2, b["Y"] + b["Height"] / 2))
        if best is None or d < best[0]:
            best = (d, w)
    return best[1] if best and best[0] < 20 else None


app = ax.app_element()
for win in ax.app_windows(app):
    plugin = ax.window_plugin_name(win)
    if not plugin:
        continue
    qw = quartz_for(win)
    if qw is None:
        print(f"\n### {plugin}: no matching Quartz window")
        continue
    img = capture_one_bestres(qw)
    words = ocr_words(img, min_conf=30)
    placed = [(w["text"], box_center_screen(w, img.size, qw)) for w in words]
    labels = [(t, p) for t, p in placed if not NUMBER.search(t) and len(t) > 1]
    values = [(t, p) for t, p in placed if NUMBER.search(t)]
    sliders = [e for e in ax.find_all(win, lambda e: ax.role(e) == "AXSlider", maxd=14) if ax.value(e) not in (None, "")]
    print(f"\n### {plugin}: {len(words)} OCR words, {len(sliders)} knobs")
    print("   OCR text:", " | ".join(t for t, _ in placed)[:400])
    for e in sliders[:14]:
        c = ax.center(e)
        if c is None:
            continue
        above = [tp for tp in labels if tp[1][1] < c[1]]
        below = [tp for tp in values if tp[1][1] > c[1]]
        lab = min(above or labels, key=lambda tp: math.dist(c, tp[1]), default=None)
        val = min(below or values, key=lambda tp: math.dist(c, tp[1]), default=None)
        name = ax.desc(e) or "-"
        print(f"   knob at ({c[0]:.0f},{c[1]:.0f}) ax-name={name!r:12} ax-shown={ax.ax_get(e, 'AXValueDescription')!r:12} "
              f"-> label {lab[0] if lab else None!r} ({math.dist(c, lab[1]):.0f}pt)" if lab else "",
              f"value {val[0] if val else None!r} ({math.dist(c, val[1]):.0f}pt)" if val else "")
