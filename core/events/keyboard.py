"""Synthetic keyboard input (US ANSI layout): shortcuts, single keys, type-select."""
import time

import Quartz

from core.events.stop import check_stop
from core.events.tag import tag_synthetic


KEY_TAP_S = 0.01          # between key down and key up
TYPE_CHAR_S = 0.03        # between characters while type-selecting


CHAR_KEYCODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8,
    "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25,
    "7": 26, "-": 27, "8": 28, "0": 29, "]": 30, "o": 31, "u": 32, "[": 33,
    "i": 34, "p": 35, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42,
    ",": 43, "/": 44, "n": 45, "m": 46, ".": 47, "`": 50, " ": 49,
}

NAMED_KEYS = {
    "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51,
    "esc": 53, "escape": 53,
    "left": 123, "right": 124, "down": 125, "up": 126,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
}

MOD_FLAGS = {
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
        flag = MOD_FLAGS.get(mod.lower())
        if flag is None:
            raise ValueError(f"unknown modifier {mod!r} in {spec!r}")
        flags |= flag
    keycode = NAMED_KEYS.get(key)
    if keycode is None:
        keycode = CHAR_KEYCODES.get(key)
    if keycode is None:
        raise ValueError(f"unknown key {parts[-1]!r} in {spec!r}")
    return keycode, flags


def post_key(keycode: int, flags: int = 0, stop_event=None) -> None:
    for down in (True, False):
        check_stop(stop_event)
        ev = Quartz.CGEventCreateKeyboardEvent(None, keycode, down)
        Quartz.CGEventSetFlags(ev, flags)
        tag_synthetic(ev)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(KEY_TAP_S)


def press(spec: str, stop_event=None) -> None:
    keycode, flags = parse_shortcut(spec)
    post_key(keycode, flags, stop_event)


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
        check_stop(stop_event)
        keycode = CHAR_KEYCODES.get(ch.lower())
        if keycode is not None:
            post_key(keycode, stop_event=stop_event)
        else:
            # Unmapped char (unicode) — post it as a literal string event.
            for down in (True, False):
                ev = Quartz.CGEventCreateKeyboardEvent(None, 0, down)
                Quartz.CGEventKeyboardSetUnicodeString(ev, len(ch), ch)
                tag_synthetic(ev)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(TYPE_CHAR_S)
