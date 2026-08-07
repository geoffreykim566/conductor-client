"""Locate the Logic Pro window and capture it (macOS)."""
import Quartz
from PIL import Image

from config import LOGIC_PRO_APP_NAMES


def _find_all_logic_pro_windows() -> list[dict]:
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


def _capture_one_bestres(win_info: dict) -> Image.Image | None:
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


def capture_all_plugin_windows() -> list[tuple[Image.Image, dict]]:
    """Capture every open Logic plugin editor at best-res for OCR.

    Returns [(RGB image, window_info), ...]. Empty list when Logic isn't running
    or no plugin editors are open. Per-window capture avoids the union-rect
    coordinate issue that affects the composite LLM-vision capture (C2).
    """
    try:
        wins = _find_all_logic_pro_windows()
    except RuntimeError:
        return []
    # Plugin editor windows have no kCGWindowName. Secondary Logic dialogs (e.g.
    # "Untitled - Project Settings") use Logic's " - " naming convention. App-level
    # settings/preferences windows (Logic Pro → Settings → Audio) use titles like
    # "Logic Pro Settings" (10.8+) or "Logic Pro Preferences" (≤10.7). The main
    # project window is just the project filename with no " - " / "Settings" /
    # "Preferences", so it stays excluded.
    plugins = [w for w in wins
               if not w.get("kCGWindowName", "")
               or " - " in w.get("kCGWindowName", "")
               or "Settings" in w.get("kCGWindowName", "")
               or "Preferences" in w.get("kCGWindowName", "")]
    result = []
    for w in plugins:
        b = w["kCGWindowBounds"]
        if b.get("Width", 0) < 100 or b.get("Height", 0) < 100:
            continue
        img = _capture_one_bestres(w)
        if img is not None:
            result.append((img, w))
    return result


def capture_window_bestres() -> tuple[Image.Image, dict]:
    """Capture the frontmost plugin editor at best-res (smallest floating window).

    For multi-window locate use capture_all_plugin_windows() instead — it searches
    all open editors and picks by OCR identity rather than window area.
    """
    wins = _find_all_logic_pro_windows()
    floats = [w for w in wins if w.get("kCGWindowLayer") == 8] or wins
    target = min(
        floats,
        key=lambda w: w["kCGWindowBounds"]["Width"] * w["kCGWindowBounds"]["Height"],
    )
    img = _capture_one_bestres(target)
    if img is None:
        raise RuntimeError(
            "Failed to capture Logic Pro window. Grant Screen Recording permission "
            "in System Settings → Privacy & Security."
        )
    return img, target


def capture_menubar_strip() -> tuple[Image.Image, float] | None:
    """Capture the top 50pt of the display holding Logic Pro's window
    (covers the macOS menu bar).

    Not necessarily the main display: with "Displays have separate Spaces"
    enabled, each display shows its own active Space's menu bar, so a
    multi-monitor setup with Logic Pro on a non-main display would otherwise
    always capture the wrong display's menu bar (e.g. reading whatever app
    is frontmost on the main display instead).

    Returns (PIL RGB image, screen_height_in_points) or None on failure.
    The image is at native display resolution (2x pixels per point on Retina),
    so divide pixel x/y coords by the display scale to get screen points.
    """
    display_id = Quartz.CGMainDisplayID()
    try:
        wins = _find_all_logic_pro_windows()
        if wins:
            main_win = max(wins, key=lambda w: w["kCGWindowBounds"]["Width"] * w["kCGWindowBounds"]["Height"])
            b = main_win["kCGWindowBounds"]
            cx, cy = b["X"] + b["Width"] / 2, b["Y"] + b["Height"] / 2
            _err, display_ids, count = Quartz.CGGetActiveDisplayList(16, None, None)
            for did in (display_ids or [])[:count]:
                db = Quartz.CGDisplayBounds(did)
                if (db.origin.x <= cx < db.origin.x + db.size.width
                        and db.origin.y <= cy < db.origin.y + db.size.height):
                    display_id = did
                    break
    except Exception:
        pass
    bounds = Quartz.CGDisplayBounds(display_id)
    screen_w_pt = bounds.size.width
    screen_h_pt = bounds.size.height
    rect = Quartz.CGRectMake(0, 0, screen_w_pt, 50)
    cg = Quartz.CGDisplayCreateImageForRect(display_id, rect)
    if cg is None:
        return None
    pw = Quartz.CGImageGetWidth(cg)
    ph = Quartz.CGImageGetHeight(cg)
    bpr = Quartz.CGImageGetBytesPerRow(cg)
    data = bytes(Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(cg)))
    img = Image.frombuffer("RGBA", (pw, ph), data, "raw", "BGRA", bpr, 1).convert("RGB")
    return img, screen_h_pt
