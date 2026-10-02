"""Open Logic's menu-bar menus and wait on its popup-menu windows."""
import time

import Quartz
from PIL import Image

from config import LOGIC_PRO_APP_NAMES
from core.automation.errors import StepAbort
from core.automation.fuzzy_match import fuzzy_match_menu_item
from core.automation.logic_focus import logic_display
from core.automation.timing import VERIFY_INTERVAL_S, VERIFY_TIMEOUT_S
from core.capture.ocr_vision import ocr_words
from core.events.mouse import click_at
from core.events.stop import check_stop


def find_logic_menu_windows() -> list[dict]:
    """Return all on-screen Logic Pro popup menu windows (layer 101)."""
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    return [
        w for w in window_list
        if w.get("kCGWindowLayer") == 101
        and w.get("kCGWindowOwnerName", "") in LOGIC_PRO_APP_NAMES
        and w.get("kCGWindowBounds", {}).get("Width", 0) > 20
        and w.get("kCGWindowBounds", {}).get("Height", 0) > 20
    ]


def open_menubar_menu(title: str, stop_event=None) -> None:
    """Open a top-level menu by clicking its menu-bar title.

    Chosen over Ctrl+F2 keyboard focus: proven not to fire on at least one
    test machine (system shortcut disabled/intercepted), while the menu bar
    is always clickable. Menu-bar text renders on a translucent strip, so
    OCR runs at min_conf=20.

    """
    check_stop(stop_event)
    display_id, bounds = logic_display()
    rect = Quartz.CGRectMake(0, 0, bounds.size.width, 40)
    cg = Quartz.CGDisplayCreateImageForRect(display_id, rect)
    if cg is None:
        raise StepAbort("could not capture the menu bar strip")
    pw, ph = Quartz.CGImageGetWidth(cg), Quartz.CGImageGetHeight(cg)
    bpr = Quartz.CGImageGetBytesPerRow(cg)
    data = bytes(Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(cg)))
    img = Image.frombuffer("RGBA", (pw, ph), data, "raw", "BGRA", bpr, 1).convert("RGB")

    words = ocr_words(img, min_conf=20.0)
    box = fuzzy_match_menu_item(title, words)
    if box is None:
        raise StepAbort(
            f"menu-bar title {title!r} not found "
            f"(ocr_saw={[w['text'] for w in words]})")
    scale = pw / bounds.size.width
    x = bounds.origin.x + (box["left"] + box["width"] / 2) / scale
    y = bounds.origin.y + (box["top"] + box["height"] / 2) / scale
    count = menu_window_count()
    click_at(x, y, stop_event)
    if not wait_menu_count(count + 1):
        raise StepAbort(f"menu {title!r} did not open after clicking its title")


def menu_window_count() -> int:
    return len(find_logic_menu_windows())


def wait_menu_count(min_count: int, timeout: float = VERIFY_TIMEOUT_S) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if menu_window_count() >= min_count:
            return True
        time.sleep(VERIFY_INTERVAL_S)
    return False


def wait_menus_gone(timeout: float = VERIFY_TIMEOUT_S) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if menu_window_count() == 0:
            return True
        time.sleep(VERIFY_INTERVAL_S)
    return False
