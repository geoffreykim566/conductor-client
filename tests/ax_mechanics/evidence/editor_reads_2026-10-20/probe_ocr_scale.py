"""Probe: does upscaling a plug-in editor's capture (or lowering Vision's minimum text height) make
its OCR better? For every open plug-in window in editor view, OCR the same capture at 1x/2x/3x
(Lanczos) with Vision's default and a zero minimum text height, print every line read, and save
the images next to this script. Read-only: no mouse, no clicks."""
import math
import sys
from pathlib import Path

import Quartz
import Vision
from PIL import Image

sys.path.insert(0, "/Users/geoffreykim/Desktop/conductor/client")
from core import ax  # noqa: E402
from core.capture.ocr_vision import _cgimage_from_pil  # noqa: E402
from core.capture.window_capture import capture_one_bestres, find_all_logic_pro_windows  # noqa: E402

OUT = Path(__file__).parent / "ocr_scale"


def quartz_for(win):
    c = ax.center(win)
    best = None
    for w in find_all_logic_pro_windows():
        b = w["kCGWindowBounds"]
        d = math.dist(c, (b["X"] + b["Width"] / 2, b["Y"] + b["Height"] / 2))
        if best is None or d < best[0]:
            best = (d, w)
    return best[1] if best and best[0] < 20 else None


def lines(img, min_h=None):
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)
    if min_h is not None:
        req.setMinimumTextHeight_(min_h)
    h = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(_cgimage_from_pil(img), None)
    h.performRequests_error_([req], None)
    out = []
    for obs in req.results() or []:
        c = obs.topCandidates_(1)
        if c:
            bb = obs.boundingBox()
            out.append((round(1 - bb.origin.y - bb.size.height, 3), round(bb.origin.x, 3), c[0].string(), round(c[0].confidence(), 2)))
    return sorted(out)


OUT.mkdir(exist_ok=True)
app = ax.app_element()
for win in ax.app_windows(app):
    plugin = ax.window_plugin_name(win)
    if not plugin or ax.current_view(win) == "Controls":
        continue
    qw = quartz_for(win)
    img = capture_one_bestres(qw) if qw else None
    if img is None:
        print(f"\n### {plugin}: no capture")
        continue
    print(f"\n### {plugin} (view {ax.current_view(win)!r}, capture {img.size[0]}x{img.size[1]}, "
          f"default min text height {Vision.VNRecognizeTextRequest.alloc().init().minimumTextHeight():.4f})")
    for scale in (1, 2, 3):
        im = img if scale == 1 else img.resize((img.size[0] * scale, img.size[1] * scale), Image.LANCZOS)
        im.save(OUT / f"{plugin.replace(' ', '_')}_x{scale}.png")
        for min_h in (None, 0.0):
            got = lines(im, min_h)
            print(f"  x{scale} min_h={'default' if min_h is None else min_h}: {len(got)} lines")
            print("     " + " | ".join(f"{t}({c})" for _, _, t, c in got))
