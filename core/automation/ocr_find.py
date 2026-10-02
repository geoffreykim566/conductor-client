"""Find text on Logic's windows by capture + OCR, and map OCR boxes to screen points."""
import time

from core.automation.fuzzy_match import fuzzy_match_menu_item
from core.automation.menus import find_logic_menu_windows
from core.automation.timing import VERIFY_INTERVAL_S, VERIFY_TIMEOUT_S
from core.capture.ocr_vision import ocr_words
from core.capture.window_capture import capture_one_bestres, find_all_logic_pro_windows


def _capture_candidates(include_menus: bool = True) -> list[tuple]:
    """[(img, win_info)] for every Logic window worth searching, smallest
    first — dialogs/pickers before the main project window, so a dense
    arrange view never shadows a settings row with the same words."""
    out = []
    try:
        wins = find_all_logic_pro_windows()
    except RuntimeError:
        wins = []
    if include_menus:
        wins = wins + find_logic_menu_windows()
    wins.sort(key=lambda w: (w["kCGWindowBounds"]["Width"]
                             * w["kCGWindowBounds"]["Height"]))
    for w in wins:
        img = capture_one_bestres(w)
        if img is not None:
            out.append((img, w))
    return out


def find_text(texts: list[str], include_menus: bool = True) -> dict | None:
    """First fuzzy hit for any of `texts` across candidate windows.
    Returns {text, box, img, win, words} or None."""
    for img, win in _capture_candidates(include_menus):
        words = ocr_words(img)
        if not words:
            continue
        for text in texts:
            box = fuzzy_match_menu_item(text, words)
            if box is not None:
                return {"text": text, "box": box, "img": img,
                        "win": win, "words": words}
    return None


def wait_for_text(texts: list[str], timeout: float = VERIFY_TIMEOUT_S,
                   include_menus: bool = True) -> dict | None:
    deadline = time.monotonic() + timeout
    last_seen: list = []
    while time.monotonic() < deadline:
        hit = find_text(texts, include_menus)
        if hit is not None:
            return hit
        time.sleep(VERIFY_INTERVAL_S)
    # Miss: dump what OCR actually saw so a marker gap isn't confused with
    # a mechanism failure.
    for img, win in _capture_candidates(include_menus):
        last_seen.extend(w["text"] for w in ocr_words(img))
    print(f"[executor] verify miss for {texts!r}; ocr_saw={last_seen}")
    return None


def box_center_screen(box: dict, img_size: tuple, win_info: dict) -> tuple:
    """OCR pixel box -> global screen points (same math as the overlay's
    _position_on_screen — pixel coords normalized by image dims, scaled into
    the window's point bounds)."""
    b = win_info["kCGWindowBounds"]
    cx = b["X"] + ((box["left"] + box["width"] / 2) / img_size[0]) * b["Width"]
    cy = b["Y"] + ((box["top"] + box["height"] / 2) / img_size[1]) * b["Height"]
    return cx, cy


def is_front_window(win: dict) -> bool:
    """Whether `win` is Logic's front window among those on its layer.
    Window capture reads a window's contents even when another covers it, so
    a row "showing" in Project Settings under the Settings window isn't
    clickable (see README "Covered panes"). Floating plugin windows sit on
    another layer and don't count."""

    try:
        wins = find_all_logic_pro_windows()   # front to back
    except RuntimeError:
        return False
    layer = win.get("kCGWindowLayer", 0)
    front = next((w for w in wins if w.get("kCGWindowLayer", 0) == layer), None)
    return front is not None and front.get("kCGWindowNumber") == win.get("kCGWindowNumber")


def value_blob_right_of(label_box: dict, words: list[dict]) -> dict | None:
    """The control's current-value text sitting right of a settings label:
    nearest same-row word right of the label, extended over adjacent words
    (gaps under 2x word height) into one union box."""
    label_cy = label_box["top"] + label_box["height"] / 2
    label_right = label_box["left"] + label_box["width"]
    row = [w for w in words
           if w["left"] >= label_right
           and abs((w["top"] + w["height"] / 2) - label_cy)
           <= max(label_box["height"], w["height"]) * 0.8]
    if not row:
        return None
    row.sort(key=lambda w: w["left"])
    blob = [row[0]]
    for w in row[1:]:
        prev = blob[-1]
        if w["left"] - (prev["left"] + prev["width"]) <= prev["height"] * 2:
            blob.append(w)
        else:
            break
    left = min(w["left"] for w in blob)
    top = min(w["top"] for w in blob)
    right = max(w["left"] + w["width"] for w in blob)
    bottom = max(w["top"] + w["height"] for w in blob)
    return {"left": left, "top": top, "width": right - left,
            "height": bottom - top,
            "label": " ".join(w["text"] for w in blob)}
