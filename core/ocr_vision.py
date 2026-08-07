"""Apple Vision OCR backend (production, client-side — Vision is macOS-local).

Promoted from server/diagnostics/_ocr_vision.py after S3b proved parity (conf 100
across 5 plugins, both tesseract misses recovered). Returns word dicts
[{text,left,top,width,height,conf}] in top-left pixel space — the shape the S2
matching layer (core/matching.py) consumes.

Vision returns boxes NORMALIZED (0..1) with a BOTTOM-LEFT origin; we convert to
top-left pixels here so everything downstream sees one convention:
    left   = bx * W
    top    = (1 - by - bh) * H      # Y-flip: bottom-left → top-left
    width  = bw * W
    height = bh * H
Confidence is Vision's per-line string confidence (0..1) scaled to 0..100; a
per-word value isn't exposed, so the line value applies to each word it contains.
"""
import io

import Quartz
import Vision
from Foundation import NSData, NSMakeRange
from PIL import Image


def _cgimage_from_pil(img: Image.Image):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
    src = Quartz.CGImageSourceCreateWithData(data, None)
    return Quartz.CGImageSourceCreateImageAtIndex(src, 0, None)


def ocr_words(img: Image.Image, min_conf: float = 40.0) -> list[dict]:
    """Return [{text,left,top,width,height,conf}] in top-left pixel space."""
    cg = _cgimage_from_pil(img)
    W = Quartz.CGImageGetWidth(cg)
    H = Quartz.CGImageGetHeight(cg)

    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)  # plugin labels aren't prose; no autocorrect

    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg, None)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError(f"Vision performRequests failed: {err}")

    words: list[dict] = []
    for obs in req.results() or []:
        cands = obs.topCandidates_(1)
        if not cands:
            continue
        rec = cands[0]
        s = rec.string()
        conf = float(rec.confidence()) * 100.0
        if conf < min_conf:
            continue
        # Per-word boxes: locate each token's char range and ask Vision for its box.
        idx = 0
        for token in s.split():
            start = s.find(token, idx)
            if start < 0:
                continue
            idx = start + len(token)
            box_obs, e = rec.boundingBoxForRange_error_(NSMakeRange(start, len(token)), None)
            if box_obs is None:
                continue
            bb = box_obs.boundingBox()
            bx, by = bb.origin.x, bb.origin.y
            bw, bh = bb.size.width, bb.size.height
            words.append({
                "text": token,
                "conf": conf,
                "left": int(round(bx * W)),
                "top": int(round((1.0 - by - bh) * H)),  # bottom-left → top-left
                "width": int(round(bw * W)),
                "height": int(round(bh * H)),
            })
    return words
