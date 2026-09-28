"""One-shot walkthrough executor (control spike).

Executes a navigation path as synthetic input instead of watching the user
perform it (`core.walkthrough_poller`). The inversion removes continuous
polling: after every action we know exactly what should be on screen and
when, so verification is one capture at a known moment with a known expected
answer — retried briefly, then a hard abort. Never a blind continue.

Step kinds:
  key            — post a keyboard shortcut ("Cmd+F", "Option+K", ...)
  menu           — click the menu-bar title to open the top-level menu
                   (Ctrl+F2 keyboard focus proved unreliable — dead on at
                   least one machine), then per-hop type-select +
                   Right/Return. Item NAMES are typed, never positional
                   arrow counts — names are what the KB verifies, and menu
                   contents shift across Logic versions/contexts.
  click_text     — one capture+OCR, click the box of a matched string.
                   `value` is a list (option set): a state-dependent dropdown
                   matches whichever member is currently displayed.
  click_value_of — find a settings-row LABEL, click the value blob to its
                   right (the label itself is inert text; the control beside
                   it is what takes the click).
  choose         — a dropdown the previous step just opened: pick `value` (an
                   option, or "larger"/"smaller" = one step from the checked
                   item) from the open menu via AX, then read the row back.
                   Escape out when value is None (the spike-safe default).

Any step may carry:
  expect  — list[str]; after acting, wait until one is visible somewhere in
            Logic's windows (abort on timeout). None/absent = no OCR verify.
  final   — marks the state-changing step (logged; the in-app confirm UX is
            a product problem, not a spike one — see diag_executor docstring).

Requires the Accessibility permission (synthetic-event posting) on top of the
existing Screen Recording. Every event batch is preceded by a frontmost-app
check: if Logic Pro isn't frontmost the path aborts rather than typing into
whatever is.
"""
import time

import Quartz

from config import LOGIC_PRO_APP_NAMES
from core.menu_watcher import _find_logic_menu_windows, _fuzzy_match_menu_item
from core.ocr_vision import ocr_words
from core.window_capture import _capture_one_bestres, _find_all_logic_pro_windows

KEY_TAP_S = 0.01          # between key down and key up
TYPE_CHAR_S = 0.03        # between characters while type-selecting
ACTION_SETTLE_S = 0.15    # after a shortcut/click before the next action
MENU_SETTLE_S = 0.35      # after opening a menu / focusing the menu bar
VERIFY_TIMEOUT_S = 2.5    # per-step act→verify window
VERIFY_INTERVAL_S = 0.2


class StepAbort(RuntimeError):
    """A step failed its act→verify contract; the path must stop here."""


class _Stopped(Exception):
    """Internal unwind signal for a mid-step stop_event; caught inside
    run_steps() and never propagated as a StepAbort/failure."""


# Marks every CGEvent Conductor itself posts, so core.interrupt_tap's
# CGEventTap can tell "our own synthetic keystroke" from "genuinely real
# input" — without this, a preemptive any-key interrupt would abort a
# walkthrough on its own first synthetic keystroke, every time.
SYNTHETIC_EVENT_TAG = 0x434F4E44  # "COND" in ASCII, arbitrary marker


def _tag_synthetic(event) -> None:
    Quartz.CGEventSetIntegerValueField(event, Quartz.kCGEventSourceUserData, SYNTHETIC_EVENT_TAG)


def _check_stop(stop_event) -> None:
    if stop_event is not None and stop_event.is_set():
        raise _Stopped()


# ---------------------------------------------------------------------------
# Key + mouse synthesis (US ANSI layout)

_CHAR_KEYCODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8,
    "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25,
    "7": 26, "-": 27, "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33,
    "i": 34, "p": 35, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42,
    ",": 43, "/": 44, "n": 45, "m": 46, ".": 47, "`": 50, " ": 49,
}

_NAMED_KEYS = {
    "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51,
    "esc": 53, "escape": 53,
    "left": 123, "right": 124, "down": 125, "up": 126,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
}

_MOD_FLAGS = {
    "cmd": Quartz.kCGEventFlagMaskCommand,
    "command": Quartz.kCGEventFlagMaskCommand,
    "shift": Quartz.kCGEventFlagMaskShift,
    "option": Quartz.kCGEventFlagMaskAlternate,
    "opt": Quartz.kCGEventFlagMaskAlternate,
    "alt": Quartz.kCGEventFlagMaskAlternate,
    "ctrl": Quartz.kCGEventFlagMaskControl,
    "control": Quartz.kCGEventFlagMaskControl,
}


def parse_shortcut(spec: str) -> tuple[int, int]:
    """"Ctrl+F2" / "Cmd+F" / "I" -> (virtual keycode, modifier flags)."""
    parts = [p.strip() for p in spec.split("+") if p.strip()]
    if not parts:
        raise ValueError(f"empty shortcut {spec!r}")
    key = parts[-1].lower()
    flags = 0
    for mod in parts[:-1]:
        flag = _MOD_FLAGS.get(mod.lower())
        if flag is None:
            raise ValueError(f"unknown modifier {mod!r} in {spec!r}")
        flags |= flag
    keycode = _NAMED_KEYS.get(key)
    if keycode is None:
        keycode = _CHAR_KEYCODES.get(key)
    if keycode is None:
        raise ValueError(f"unknown key {parts[-1]!r} in {spec!r}")
    return keycode, flags


def _post_key(keycode: int, flags: int = 0, stop_event=None) -> None:
    for down in (True, False):
        _check_stop(stop_event)
        ev = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
        Quartz.CGEventSetFlags(ev, flags)
        _tag_synthetic(ev)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(KEY_TAP_S)


def press(spec: str, stop_event=None) -> None:
    keycode, flags = parse_shortcut(spec)
    _post_key(keycode, flags, stop_event)


def type_select(text: str, stop_event=None) -> None:
    """Type `text` to drive macOS type-select in a focused menu/menu bar.

    Trailing ellipsis/periods are stripped ("Plug-in Manager…" — type-select
    matches without them). Spaces ARE typed: NSMenu's incremental search
    includes them (e.g. typing "project s" narrows to "Project Settings").
    If a machine ever treats space as activate-item, this is the constant to
    revisit (fallback: type first word only, arrow the rest).
    """
    cleaned = text.rstrip(".").rstrip("…").strip()
    for ch in cleaned:
        _check_stop(stop_event)
        keycode = _CHAR_KEYCODES.get(ch.lower())
        if keycode is not None:
            _post_key(keycode, stop_event=stop_event)
        else:
            # Unmapped char (unicode) — post it as a literal string event.
            for down in (True, False):
                ev = Quartz.CGEventCreateKeyboardEvent(None, 0, down)
                Quartz.CGEventKeyboardSetUnicodeString(ev, len(ch), ch)
                _tag_synthetic(ev)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(TYPE_CHAR_S)


def click_at(x_pt: float, y_pt: float, stop_event=None) -> None:
    """Left-click at global screen-point coords (same top-left-origin space
    as kCGWindowBounds, so window-relative math feeds this directly)."""
    _check_stop(stop_event)
    point = (x_pt, y_pt)
    move = Quartz.CGEventCreateMouseEvent(
        None, Quartz.kCGEventMouseMoved, point, Quartz.kCGMouseButtonLeft)
    _tag_synthetic(move)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, move)
    time.sleep(0.05)
    for kind in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
        ev = Quartz.CGEventCreateMouseEvent(
            None, kind, point, Quartz.kCGMouseButtonLeft)
        _tag_synthetic(ev)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(KEY_TAP_S)


def check_event_permission(prompt: bool = True) -> bool:
    """True if synthetic-event posting is allowed (Accessibility granted)."""
    preflight = getattr(Quartz, "CGPreflightPostEventAccess", None)
    if preflight is None:
        return True  # too old to check — attempt and observe
    if preflight():
        return True
    if prompt:
        Quartz.CGRequestPostEventAccess()
    return False


# ---------------------------------------------------------------------------
# Perception (one-shot, at known moments)

def _frontmost_owner() -> str:
    try:
        from AppKit import NSWorkspace
        from Foundation import NSDate, NSRunLoop
        # NSWorkspace state only refreshes as the run loop runs, and a
        # headless script never pumps it — without this the answer stays
        # frozen at whatever was frontmost when the process launched (i.e.
        # always the terminal, even with Logic visibly in front).
        NSRunLoop.currentRunLoop().runUntilDate_(
            NSDate.dateWithTimeIntervalSinceNow_(0.05))
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return str(app.localizedName()) if app else ""
    except Exception:
        # Fallback: frontmost layer-0 window in z-order.
        wins = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID) or []
        for w in wins:
            if w.get("kCGWindowLayer") == 0:
                return w.get("kCGWindowOwnerName", "")
        return ""


def activate_logic(timeout: float = 3.0) -> bool:
    """Bring the running Logic Pro to the front; True once it's frontmost.

    Conductor-side activation of an already-running app (NSRunningApplication)
    — not Logic lifecycle automation, so no Automation permission involved.
    """
    try:
        from AppKit import NSWorkspace
    except Exception:
        return False
    apps = NSWorkspace.sharedWorkspace().runningApplications()
    target = next((a for a in apps
                   if str(a.localizedName()) in LOGIC_PRO_APP_NAMES), None)
    if target is None:
        return False
    # NSApplicationActivateIgnoringOtherApps (2): deprecated on 14+, but the
    # plain cooperative request is exactly what gets ignored when another
    # app (the terminal running this script) is active.
    target.activateWithOptions_(2)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _frontmost_owner() in LOGIC_PRO_APP_NAMES:
            return True
        time.sleep(0.1)
    return False


def wait_logic_on_screen(timeout: float = 2.0) -> bool:
    """Whether a Logic window is on screen within `timeout`. activate_logic()
    returns as soon as Logic is the frontmost app, but with Logic on another
    desktop its windows are still sliding in: a capture then finds nothing, a
    toggle pre-check reads that as "not showing" and presses the key -- which
    closed an open Inspector (found live 2026-09-28)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if _find_all_logic_pro_windows():
                return True
        except RuntimeError:
            pass
        time.sleep(0.1)
    return False


def _require_logic_frontmost() -> None:
    owner = _frontmost_owner()
    if owner not in LOGIC_PRO_APP_NAMES:
        raise StepAbort(
            f"Logic Pro is not frontmost (frontmost: {owner!r}) — "
            "refusing to post events")


def _capture_candidates(include_menus: bool = True) -> list[tuple]:
    """[(img, win_info)] for every Logic window worth searching, smallest
    first — dialogs/pickers before the main project window, so a dense
    arrange view never shadows a settings row with the same words."""
    out = []
    try:
        wins = _find_all_logic_pro_windows()
    except RuntimeError:
        wins = []
    if include_menus:
        wins = wins + _find_logic_menu_windows()
    wins.sort(key=lambda w: (w["kCGWindowBounds"]["Width"]
                             * w["kCGWindowBounds"]["Height"]))
    for w in wins:
        img = _capture_one_bestres(w)
        if img is not None:
            out.append((img, w))
    return out


def _find_text(texts: list[str], include_menus: bool = True) -> dict | None:
    """First fuzzy hit for any of `texts` across candidate windows.
    Returns {text, box, img, win, words} or None."""
    for img, win in _capture_candidates(include_menus):
        words = ocr_words(img)
        if not words:
            continue
        for text in texts:
            box = _fuzzy_match_menu_item(text, words)
            if box is not None:
                return {"text": text, "box": box, "img": img,
                        "win": win, "words": words}
    return None


def _wait_for_text(texts: list[str], timeout: float = VERIFY_TIMEOUT_S,
                   include_menus: bool = True) -> dict | None:
    deadline = time.monotonic() + timeout
    last_seen: list = []
    while time.monotonic() < deadline:
        hit = _find_text(texts, include_menus)
        if hit is not None:
            return hit
        time.sleep(VERIFY_INTERVAL_S)
    # Miss: dump what OCR actually saw so a marker gap isn't confused with
    # a mechanism failure (same idea as the poller's miss dump).
    for img, win in _capture_candidates(include_menus):
        last_seen.extend(w["text"] for w in ocr_words(img))
    print(f"[executor] verify miss for {texts!r}; ocr_saw={last_seen}")
    return None


def _logic_display() -> tuple[int, object]:
    """(display_id, CGDisplayBounds) of the display holding Logic's largest
    window — NOT necessarily the main display (multi-monitor setups put the
    menu bar Logic responds to on Logic's own display)."""
    display_id = Quartz.CGMainDisplayID()
    try:
        wins = _find_all_logic_pro_windows()
        main_win = max(wins, key=lambda w: (w["kCGWindowBounds"]["Width"]
                                            * w["kCGWindowBounds"]["Height"]))
        b = main_win["kCGWindowBounds"]
        cx, cy = b["X"] + b["Width"] / 2, b["Y"] + b["Height"] / 2
        _err, ids, count = Quartz.CGGetActiveDisplayList(16, None, None)
        for did in (ids or [])[:count]:
            db = Quartz.CGDisplayBounds(did)
            if (db.origin.x <= cx < db.origin.x + db.size.width
                    and db.origin.y <= cy < db.origin.y + db.size.height):
                display_id = did
                break
    except Exception:
        pass
    return display_id, Quartz.CGDisplayBounds(display_id)


def _open_menubar_menu(title: str, stop_event=None) -> None:
    """Open a top-level menu by clicking its menu-bar title.

    Chosen over Ctrl+F2 keyboard focus: proven not to fire on at least one
    test machine (system shortcut disabled/intercepted), while the menu bar
    is always clickable. Menu-bar text renders on a translucent strip, so
    OCR runs at min_conf=20 (same reasoning as diag_menu_capture).
    """
    _check_stop(stop_event)
    display_id, bounds = _logic_display()
    rect = Quartz.CGRectMake(0, 0, bounds.size.width, 40)
    cg = Quartz.CGDisplayCreateImageForRect(display_id, rect)
    if cg is None:
        raise StepAbort("could not capture the menu bar strip")
    import io
    from PIL import Image
    pw, ph = Quartz.CGImageGetWidth(cg), Quartz.CGImageGetHeight(cg)
    bpr = Quartz.CGImageGetBytesPerRow(cg)
    data = bytes(Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(cg)))
    img = Image.frombuffer("RGBA", (pw, ph), data, "raw", "BGRA", bpr, 1).convert("RGB")

    words = ocr_words(img, min_conf=20.0)
    box = _fuzzy_match_menu_item(title, words)
    if box is None:
        raise StepAbort(
            f"menu-bar title {title!r} not found "
            f"(ocr_saw={[w['text'] for w in words]})")
    scale = pw / bounds.size.width
    x = bounds.origin.x + (box["left"] + box["width"] / 2) / scale
    y = bounds.origin.y + (box["top"] + box["height"] / 2) / scale
    count = _menu_window_count()
    click_at(x, y, stop_event)
    if not _wait_menu_count(count + 1):
        raise StepAbort(f"menu {title!r} did not open after clicking its title")


def _menu_window_count() -> int:
    return len(_find_logic_menu_windows())


def _wait_menu_count(min_count: int, timeout: float = VERIFY_TIMEOUT_S) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _menu_window_count() >= min_count:
            return True
        time.sleep(VERIFY_INTERVAL_S)
    return False


def _wait_menus_gone(timeout: float = VERIFY_TIMEOUT_S) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _menu_window_count() == 0:
            return True
        time.sleep(VERIFY_INTERVAL_S)
    return False


def _box_center_screen(box: dict, img_size: tuple, win_info: dict) -> tuple:
    """OCR pixel box -> global screen points (same math as the overlay's
    _position_on_screen — pixel coords normalized by image dims, scaled into
    the window's point bounds)."""
    b = win_info["kCGWindowBounds"]
    cx = b["X"] + ((box["left"] + box["width"] / 2) / img_size[0]) * b["Width"]
    cy = b["Y"] + ((box["top"] + box["height"] / 2) / img_size[1]) * b["Height"]
    return cx, cy


def _value_blob_right_of(label_box: dict, words: list[dict]) -> dict | None:
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


# ---------------------------------------------------------------------------
# Step handlers

def _verify_expect(step: dict, log) -> None:
    expect = step.get("expect")
    if not expect:
        log("    verify: none declared — check manually")
        return
    hit = _wait_for_text(expect)
    if hit is None:
        raise StepAbort(f"expected one of {expect!r} on screen; not found")
    name = hit["win"].get("kCGWindowName", "") or f"#{hit['win']['kCGWindowNumber']}"
    log(f"    verify: found {hit['text']!r} in window {name!r}")


def _cleanup_after_interrupt(log, max_presses: int = 6) -> None:
    """Close any menu(s) left open by a mid-hop interrupt — same Escape +
    _wait_menus_gone() pattern _run_choose() already uses to escape out of a
    dropdown, looped since a multi-hop path can leave more than one level
    open. Escape presses are tagged synthetic like everything else _post_key
    posts, so this doesn't re-trigger the interrupt tap on itself."""
    for _ in range(max_presses):
        if _menu_window_count() == 0:
            return
        _post_key(_NAMED_KEYS["escape"])
        _wait_menus_gone(timeout=0.5)
    log(f"    interrupt cleanup: menus still open after {max_presses} Escape presses")


def _run_key(step: dict, log, stop_event=None) -> None:
    log(f"  key: {step['value']}")
    _require_logic_frontmost()
    # Many view shortcuts toggle (Cmd+F Show Flex, Option+T): if what this
    # step exists to reveal is already on screen, pressing would hide it.
    expect = step.get("expect")
    if expect:
        hit = _find_text(expect, include_menus=False)
        if hit is not None:
            log(f"    already showing {hit['text']!r} — skipped (it would toggle off)")
            return
    press(step["value"], stop_event)
    time.sleep(ACTION_SETTLE_S)
    _verify_expect(step, log)


def _run_menu(step: dict, log, stop_event=None) -> None:
    path = step["path"]
    log(f"  menu: {' > '.join(path)}")
    if len(path) < 2:
        raise StepAbort(f"menu path needs >= 2 items, got {path!r}")
    _require_logic_frontmost()

    _open_menubar_menu(path[0], stop_event)          # click the menu-bar title
    log(f"    open: {path[0]}")
    time.sleep(MENU_SETTLE_S)

    for hop in path[1:-1]:
        _check_stop(stop_event)
        type_select(hop, stop_event)
        time.sleep(ACTION_SETTLE_S)
        count = _menu_window_count()
        _post_key(_NAMED_KEYS["right"], stop_event=stop_event)  # enter the submenu
        if not _wait_menu_count(count + 1):
            raise StepAbort(f"submenu {hop!r} did not open")
        log(f"    open: {hop}")
        time.sleep(MENU_SETTLE_S)

    _check_stop(stop_event)
    type_select(path[-1], stop_event)
    time.sleep(ACTION_SETTLE_S)
    if step.get("final"):
        log(f"    activate (final): {path[-1]}")
    _post_key(_NAMED_KEYS["return"], stop_event=stop_event)
    _wait_menus_gone()
    _verify_expect(step, log)


def _run_click(step: dict, log, stop_event=None) -> None:
    # A disclosure click toggles (Region Inspector's "Region"): if what it
    # reveals is already showing, clicking would collapse it -- same rule as
    # _run_key.
    expect = step.get("expect")
    if step["kind"] == "click_text" and expect:
        hit = _find_text(expect, include_menus=False)
        if hit is not None:
            log(f"  click_text: {step['value']!r} — already showing {hit['text']!r}, skipped (it would toggle off)")
            return
    if step["kind"] == "click_text":
        texts = step["value"] if isinstance(step["value"], list) else [step["value"]]
        hit = _wait_for_text(texts)
        if hit is None:
            raise StepAbort(f"click_text: none of {texts!r} found on screen")
        box = hit["box"]
        found = hit["text"]
    else:  # click_value_of
        hit = _wait_for_text([step["label"]], include_menus=False)
        if hit is None:
            raise StepAbort(f"click_value_of: label {step['label']!r} not found")
        box = _value_blob_right_of(hit["box"], hit["words"])
        if box is None:
            raise StepAbort(
                f"click_value_of: no value text right of {step['label']!r} "
                f"(row OCR gap?)")
        found = f"{step['label']} -> {box['label']!r}"

    x, y = _box_center_screen(box, hit["img"].size, hit["win"])
    name = hit["win"].get("kCGWindowName", "") or f"#{hit['win']['kCGWindowNumber']}"
    log(f"  {step['kind']}: {found} in window {name!r} -> click ({x:.0f}, {y:.0f})")
    _require_logic_frontmost()
    _last_click.update(point=(x, y), shown=box.get("label") if step["kind"] == "click_value_of" else hit["text"])
    click_at(x, y, stop_event)
    time.sleep(ACTION_SETTLE_S)
    _verify_expect(step, log)


# Where the last click_text/click_value_of landed and the value it showed --
# what a following choose step finds its dropdown (and current value) by.
_last_click: dict = {}


def _num_in(text: str) -> float | None:
    import re
    m = re.search(r"\d+(?:\.\d+)?", (text or "").replace(",", ""))  # "1,024"
    return float(m.group(0)) if m else None


def _same_option(want: str, got: str) -> bool:
    """"256" vs "256 Samples", "48 kHz" vs "48kHz", "Mono" vs "Monophonic",
    "Monophonic" vs "Flex Time - Monophonic" (Logic prefixes some menu items)."""
    w, g = (want or "").strip().lower(), (got or "").strip().lower()
    if not w or not g:
        return False
    nw, ng = _num_in(w), _num_in(g)
    if nw is not None or ng is not None:
        return nw == ng
    return (w == g or g.startswith(w) or w.startswith(g)
            or g.endswith(" - " + w) or w.endswith(" - " + g))


def _exact_option(want: str, got: str) -> bool:
    """_same_option without the loose prefix: "On" is not "On + Align Bars"
    (Region Smart Tempo's options prefix each other)."""
    w, g = (want or "").strip().lower(), (got or "").strip().lower()
    if not w or not g:
        return False
    nw, ng = _num_in(w), _num_in(g)
    if nw is not None or ng is not None:
        return nw == ng
    return w == g or g.endswith(" - " + w) or w.endswith(" - " + g)


def _option_index(value: str, titles: list[str]) -> int | None:
    """The option `value` means: an exact one first, else the first loose match."""
    for same in (_exact_option, _same_option):
        idx = next((i for i, t in enumerate(titles) if same(value, t)), None)
        if idx is not None:
            return idx
    return None


def _title_for(display: str, shows: dict | None) -> str:
    """The menu title a control's short display stands for (Region Smart
    Tempo shows "Bars" for "On + Align Bars"); the display itself otherwise."""
    return next((t for t, d in (shows or {}).items() if _exact_option(d, display)), display)


def _popup_items(log, shows: dict | None = None):
    """(items, checked_index) of the dropdown the previous step opened, via AX:
    the menu under the click point (a popup opens with the current item over
    the button), else the focused menu. Checked = AXMenuItemMarkChar, else the
    item matching the value the click read. (None, None) if AX can't see it."""
    from core import ax_actions as ax
    try:
        app = ax.app_element()
    except ax.AxError:
        return None, None
    menu, _ = ax.wait_until(lambda: ax.current_menu(app, _last_click.get("point")), timeout=1.5)
    if menu is None:
        return None, None
    items = [it for it in ax.children(menu)
             if ax.title(it) and ax.ax_get(it, "AXEnabled") is not False]
    checked = next((i for i, it in enumerate(items) if ax.ax_get(it, "AXMenuItemMarkChar")), None)
    if checked is None and _last_click.get("shown"):
        titles = [ax.title(it) for it in items]
        checked = _option_index(_title_for(_last_click["shown"], shows), titles)
    log(f"    options: {[ax.title(it) for it in items]} (checked: "
        f"{ax.title(items[checked]) if checked is not None else '?'})")
    return items, checked


def _read_back(row: str | None, want: str, exact: bool = False, shows: dict | None = None) -> str | None:
    """What the row shows now: the value right of a settings label, or (a
    click_text dropdown, no label) whether `want` itself is on screen."""
    deadline = time.monotonic() + VERIFY_TIMEOUT_S
    shown = None
    while time.monotonic() < deadline:
        if row:
            hit = _find_text([row], include_menus=False)
            blob = _value_blob_right_of(hit["box"], hit["words"]) if hit else None
            shown = blob["label"] if blob else None
        else:
            # the control shows "Slicing" for the menu's "Flex Time - Slicing"
            texts = [want] + ([want.split(" - ", 1)[1]] if " - " in want else [])
            hit = _find_text(texts, include_menus=False)
            shown = hit["text"] if hit else None
        if shown is not None and (_exact_option if exact else _same_option)(want, _title_for(shown, shows)):
            return shown
        time.sleep(VERIFY_INTERVAL_S)
    return shown


def _run_choose(step: dict, choose_override: str | None, log, stop_event=None):
    value = step.get("value") or choose_override
    if not _wait_menu_count(1):
        if step.get("optional"):
            log("  choose: no dropdown appeared (click may have selected "
                "directly) — skipping")
            return None
        raise StepAbort("choose: dropdown did not open")
    if value is None:
        log("  choose: no value given — Escape out (rerun with --choose=... "
            "to actually select)")
        _require_logic_frontmost()
        _post_key(_NAMED_KEYS["escape"], stop_event=stop_event)
        _wait_menus_gone()
        return None
    from core import ax_actions as ax
    log(f"  choose: {value}")
    _require_logic_frontmost()
    shows = step.get("shows") or {}
    items, checked = _popup_items(log, shows)
    relative = value.lower() in ("larger", "smaller")

    def close(msg: str):
        _post_key(_NAMED_KEYS["escape"], stop_event=stop_event)
        _wait_menus_gone()
        log(f"    {msg}")

    if items is None:
        if relative:
            close("dropdown not readable via AX — Escaped")
            raise StepAbort(f"choose {value!r}: couldn't read the dropdown's options")
        # Absolute value, menu invisible to AX: type-select, verified by read-back.
        type_select(value, stop_event)
        time.sleep(ACTION_SETTLE_S)
        _post_key(_NAMED_KEYS["return"], stop_event=stop_event)
        prev, target = _title_for(_last_click.get("shown"), shows), value
    else:
        if relative:
            if checked is None:
                close("current value unknown — Escaped")
                raise StepAbort(f"choose {value!r}: couldn't tell which option is current")
            idx = checked + (1 if value.lower() == "larger" else -1)
            if not 0 <= idx < len(items):
                close(f"already at the {'largest' if value.lower() == 'larger' else 'smallest'} "
                      f"option ({ax.title(items[checked])}) — nothing to change")
                return None
        else:
            idx = _option_index(value, [ax.title(it) for it in items])
            if idx is None:
                close("Escaped")
                raise StepAbort(f"choose: {value!r} isn't in this dropdown "
                                f"({[ax.title(it) for it in items]})")
        prev = ax.title(items[checked]) if checked is not None else _title_for(_last_click.get("shown"), shows)
        target = ax.title(items[idx])
        if idx == checked:
            close(f"already set to {target} — nothing to change")
            return None
        ax.ax_press(items[idx])
    if not _wait_menus_gone():
        close("dropdown still open after picking — Escaped")
        raise StepAbort(f"choose: dropdown still open after selecting {target!r}")
    # a title read from the dropdown itself must read back exactly; a typed
    # value (menu invisible to AX) keeps the loose match
    same = _exact_option if items is not None else _same_option
    shown = _read_back(step.get("row"), target, exact=items is not None, shows=shows)
    if shown is None or not same(target, _title_for(shown, shows)):
        raise StepAbort(f"choose: picked {target!r} but it now reads {shown!r}")
    log(f"    {prev!r} -> {shown!r} (read back)")
    if not step.get("reopen") or not prev:
        return None   # nothing to go back through / to (the spike's --choose path)
    return {"kind": "setting_chosen", "label": f"{step.get('row') or 'setting'} back to {prev}",
            "prev": prev, "row": step.get("row"), "reopen": step["reopen"], "shows": shows}


# ---------------------------------------------------------------------------
# Wire-schema translation

# Menu parents whose sub-items open a persistent, named settings pane/tab
# (Audio, Recording, MIDI, Metronome, Smart Tempo, Plug-in Manager...) rather
# than firing an instant command/toggle (Low Latency Monitoring Mode, Bypass
# All Control Surfaces) that closes the menu and leaves nothing on screen to
# verify. Derived empirically from every terminal menu step currently in the
# KB — see project_executor_path_schema memory for the reasoning.
_TABBED_PANE_PARENTS = {"Settings", "Project Settings"}


def _anchor_text(step: dict) -> list[str] | None:
    """OCR text that appearing on screen proves `step` has become reachable —
    used to auto-derive a preceding menu/key step's `expect`. None if `step`'s
    kind has no fixed, derivable anchor (e.g. `choose`, whose value is chosen
    at runtime)."""
    kind = step["kind"]
    if kind == "click_value_of":
        return [step["label"]]
    if kind == "click_text":
        val = step["value"]
        return list(val) if isinstance(val, list) else [val]
    if kind == "menu":
        return [step["path"][0]]
    if kind == "key":
        return None  # shortcuts carry no on-screen text of their own
    return None


def _menu_terminal_expect(path: list[str]) -> list[str] | None:
    """Auto-derived `expect` for a *terminal* menu step (no following step to
    borrow anchor text from). Only Settings/Project Settings sub-tabs are
    reliably still on screen, named after the menu item, after the click —
    plain commands/toggles are not; see `_TABBED_PANE_PARENTS`."""
    if len(path) < 2 or path[-2] not in _TABBED_PANE_PARENTS:
        return None
    return [path[-1].rstrip(".").rstrip("…").strip()]


def wire_to_steps(wire_steps: list[dict]) -> list[dict]:
    """Translate server wire-schema `walkthrough_steps` into the executor's
    native step dicts (see module docstring for the `kind` vocabulary).

    Wire keys map straight to `kind`: menu_path->menu, shortcut->key,
    click_text->click_text, click_value_of->click_value_of, choose->choose
    (a dropdown route's value, 2026-09-22; carries the route as `reopen` for
    revert). Unrecognized keys are dropped rather than guessed at (mirrors the server's own stance on
    not-yet-migrated legacy path steps).

    `expect` is not KB-authored data — it's derived here. A `menu`/`key` step
    followed by another step defaults to that next step's own anchor text
    (proof the action landed somewhere useful); a terminal `menu` step falls
    back to its own last-hop name only when that's reliably still visible
    (see `_menu_terminal_expect`). A click_text step followed by a
    click_value_of row gets that row's label (a disclosure header: skipped
    when the row already shows); a wire-sent `expect` on a click_text is kept
    (the server's pane-only trim). Other click_text/click_value_of/choose
    steps never get an auto `expect` — their own pre-click OCR match, or a
    following step's structural check (menu appeared/closed), does that job
    instead.

    The last translated step is marked `final: True` (the state-changing
    step gets the confirm-gate hook) — the furthest a path goes, a `choose`
    when the route picks a dropdown value.
    """
    steps: list[dict] = []
    for wire in wire_steps:
        if "menu_path" in wire:
            steps.append({"kind": "menu", "path": list(wire["menu_path"])})
        elif "shortcut" in wire:
            steps.append({"kind": "key", "value": wire["shortcut"]})
        elif "click_value_of" in wire:
            steps.append({"kind": "click_value_of", "label": wire["click_value_of"]})
        elif "click_text" in wire:
            st = {"kind": "click_text", "value": wire["click_text"]}
            if wire.get("expect"):   # pane-only route: the dropped row it reveals
                st["expect"] = list(wire["expect"])
            steps.append(st)
        elif "ax_open_plugin" in wire:
            st = {"kind": "ax_open_plugin", "value": wire["ax_open_plugin"]}
            if wire.get("new"):
                st["new"] = True
            if wire.get("track"):
                st["track"] = wire["track"]
            steps.append(st)
        elif "ax_set_param" in wire:
            steps.append({"kind": "ax_set_param", "value": dict(wire["ax_set_param"])})
        elif "choose" in wire:
            # the row to read back is the dropdown's label (click_value_of);
            # a click_text dropdown has none -- the chosen text itself is checked
            prev = steps[-1] if steps else {}
            steps.append({"kind": "choose", "value": wire["choose"],
                          "row": prev.get("label") if prev.get("kind") == "click_value_of" else None,
                          "reopen": list(wire.get("reopen") or []),
                          # menu title -> the control's shorter display ("On + Align Bars" -> "Bars")
                          "shows": dict(wire.get("shows") or {})})

    for i, step in enumerate(steps):
        nxt = steps[i + 1] if i + 1 < len(steps) else None
        # a click that reveals a settings row (a disclosure header): the row is
        # its expect, so it's skipped when already open. Only this pairing --
        # a dropdown click_text's own label can equal the next step's anchor
        # (flex: "Flex Pitch"), where skipping would be wrong.
        if step["kind"] == "click_text" and nxt is not None and nxt["kind"] == "click_value_of":
            step["expect"] = _anchor_text(nxt)
            continue
        if step["kind"] not in ("menu", "key"):
            continue
        if nxt is not None:
            expect = _anchor_text(nxt)
        elif step["kind"] == "menu":
            expect = _menu_terminal_expect(step["path"])
        else:
            expect = None
        if expect is not None:
            step["expect"] = expect

    if steps:
        steps[-1]["final"] = True
    return steps


_HANDLERS = {
    "key": lambda step, opts, log, stop_event: _run_key(step, log, stop_event),
    "menu": lambda step, opts, log, stop_event: _run_menu(step, log, stop_event),
    "click_text": lambda step, opts, log, stop_event: _run_click(step, log, stop_event),
    "click_value_of": lambda step, opts, log, stop_event: _run_click(step, log, stop_event),
    "choose": lambda step, opts, log, stop_event: _run_choose(step, opts.get("choose"), log, stop_event),
}


def _ensure_ax_handlers() -> None:
    """AX step kinds (ax_open_plugin / ax_set_param) live in core.ax_executor,
    which imports this module -- so register them lazily, on first run."""
    if "ax_open_plugin" not in _HANDLERS:
        from core.ax_executor import register
        register(_HANDLERS)


def run_steps(steps: list[dict], *, dry_run: bool = False,
              choose_override: str | None = None, log=print, stop_event=None) -> list[dict]:
    """Execute a step list; raises StepAbort at the first failed contract.

    A set stop_event unwinds the current step early (checked at fine
    granularity inside the low-level posting functions, not just between
    steps) and returns silently after closing any menus it left open —
    mirrors the existing between-step stop semantics, just faster to react.
    """
    opts = {"choose": choose_override}
    ledger: list[dict] = []
    _ensure_ax_handlers()
    for i, step in enumerate(steps, 1):
        kind = step.get("kind")
        handler = _HANDLERS.get(kind)
        if handler is None:
            raise StepAbort(f"step {i}: unknown kind {kind!r}")
        if dry_run:
            desc = step.get("path") or step.get("value") or step.get("label")
            log(f"  [dry] step {i}/{len(steps)} {kind}: {desc}")
            continue
        t0 = time.monotonic()
        log(f"step {i}/{len(steps)}")
        if kind != "choose" and _menu_window_count() > 0:
            # Nothing should be open between steps; an open menu or dropdown
            # takes every keystroke the next step posts (found live 2026-09-22:
            # a dropdown left open by a route swallowed the plugin search's
            # Ctrl+Cmd+P). Only a choose step expects one.
            log("  a menu was left open — closing it first")
            _cleanup_after_interrupt(log)
        try:
            entry = handler(step, opts, log, stop_event)
        except _Stopped:
            log("  interrupted — closing any open menus")
            _cleanup_after_interrupt(log)
            return ledger
        if isinstance(entry, dict):
            ledger.append(entry)
        log(f"    ({time.monotonic() - t0:.2f}s)")

    return ledger

