"""Locate the Logic Pro window and capture it (macOS)."""
import base64
import io

import Quartz
from PIL import Image

from config import (
    LOGIC_PRO_APP_NAMES,
    MAX_CONTEXT_WINDOWS,
    MAX_IMAGE_LONG_EDGE,
    MAX_SCREENSHOT_B64_CHARS,
    SCREENSHOT_JPEG_QUALITY,
)


def find_all_logic_pro_windows() -> list[dict]:
    """Return all on-screen Quartz window-info dicts owned by Logic Pro, or raise."""
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )

    matches: list[dict] = []
    for w in window_list:
        owner = w.get("kCGWindowOwnerName", "")
        layer = w.get("kCGWindowLayer", 0)
        bounds = w.get("kCGWindowBounds", {})
        width = bounds.get("Width", 0)
        height = bounds.get("Height", 0)

        # Allow layers 0, 3, and 8. Logic's plugin windows sit at 0 when Logic is
        # not frontmost and jump to 3 (kCGFloatingWindowLevel) when Logic is active.
        # Layer 8 is kept for safety across Logic versions.
        if layer not in (0, 3, 8):
            continue
        if width < 50 or height < 50:
            continue
        # Match on OWNER ONLY. Logic's stock plugin popups (Channel EQ, Compressor,
        # etc.) are owned by the Logic Pro process, so this captures the main window
        # plus its floating editors. Title-based matching is deliberately NOT used:
        # any other app's window whose title merely mentions "Logic Pro" (a browser
        # tab, a docs page) would otherwise leak into the capture.
        if owner in LOGIC_PRO_APP_NAMES:
            matches.append(w)

    if not matches:
        raise RuntimeError(
            "Logic Pro window not found. Make sure Logic Pro is running and visible."
        )
    return matches


def capture_one_bestres(win_info: dict) -> Image.Image | None:
    """Capture a single window at best-res. Returns None on failure."""
    b = win_info["kCGWindowBounds"]
    rect = Quartz.CGRectMake(b["X"], b["Y"], b["Width"], b["Height"])
    cg = Quartz.CGWindowListCreateImageFromArray(
        rect, [win_info["kCGWindowNumber"]], Quartz.kCGWindowImageBestResolution
    )
    if cg is None:
        return None
    pw, ph = Quartz.CGImageGetWidth(cg), Quartz.CGImageGetHeight(cg)
    bpr = Quartz.CGImageGetBytesPerRow(cg)
    data = bytes(Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(cg)))
    return Image.frombuffer("RGBA", (pw, ph), data, "raw", "BGRA", bpr, 1).convert("RGB")


def capture_context_images_b64() -> list[str]:
    """Capture every open Logic Pro window as its own base64 JPEG, for pushing
    live visual context into a chat turn.

    Deliberately per-window, not one union-rect composite (see README
    "Per-window capture"): each plugin editor stays at native clarity.

    Largest windows first (main project window typically dominates), capped
    at MAX_CONTEXT_WINDOWS so a session with several plugin editors open
    doesn't balloon vision tokens. Best-effort: returns [] on any failure
    (Logic Pro not running, no Screen Recording permission, etc.) -- this is
    pushed context, never something a turn should block or error on.
    """
    try:
        wins = find_all_logic_pro_windows()
    except RuntimeError:
        return []
    wins = sorted(
        wins,
        key=lambda w: w["kCGWindowBounds"]["Width"] * w["kCGWindowBounds"]["Height"],
        reverse=True,
    )[:MAX_CONTEXT_WINDOWS]

    images_b64 = []
    for w in wins:
        try:
            img = capture_one_bestres(w)
        except Exception:
            continue
        if img is None:
            continue
        long_edge = max(img.size)
        if long_edge > MAX_IMAGE_LONG_EDGE:
            scale = MAX_IMAGE_LONG_EDGE / long_edge
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        # JPEG, not PNG (see README "JPEG screenshots"). CGImage captures
        # carry an alpha channel JPEG can't encode.

        img.convert("RGB").save(buf, format="JPEG", quality=SCREENSHOT_JPEG_QUALITY)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        if len(b64) > MAX_SCREENSHOT_B64_CHARS:
            # Server would drop it anyway (api.py's _validate_screenshots);
            # skipping here saves the upload and keeps the reason in our log.
            print(f"[window_capture] skipped {img.width}x{img.height} capture: "
                  f"{len(b64)} b64 chars > cap {MAX_SCREENSHOT_B64_CHARS}")
            continue
        images_b64.append(b64)
    return images_b64
