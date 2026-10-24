"""The `context_menu` step: open a target's shortcut menu (the Control-click menu) through AX and drill it."""
from __future__ import annotations

import time

import ApplicationServices as AS

from core import ax
from core.automation.errors import StepAbort
from core.automation.menus import find_logic_menu_windows, wait_menus_gone
from core.automation.timing import VERIFY_TIMEOUT_S
from core.events.stop import check_stop

# AXShowMenu blocks while the menu is open and returns -25204 when AX stops waiting
# (~1.5 s by default); the menu is up long before that, so don't wait on the call.
SHOW_MENU_TIMEOUT_S = 0.3


def _targets(mw, on: str, name: str | None):
    if on == "region":
        return ax.target_region(mw, name=name)
    raise StepAbort(f"context menu target {on!r} isn't supported by this version")


def open_menu_element():
    """The open popup menu's AXMenu, found through its window's bounds (whatever the
    window size or scroll, and wherever the target sits), or None."""
    for w in find_logic_menu_windows():
        b = w["kCGWindowBounds"]
        node = ax.element_at(b["X"] + b["Width"] / 2, b["Y"] + b["Height"] / 2)
        for _ in range(8):
            if node is None:
                break
            if ax.role(node) == "AXMenu":
                return node
            node = ax.parent(node)
    return None


def open_context_menu(el, log):
    """AXShowMenu on `el` (it selects a region too, so a named region needn't be selected
    first); if no menu comes up, a Control-click on its visible part."""
    AS.AXUIElementSetMessagingTimeout(el, SHOW_MENU_TIMEOUT_S)
    AS.AXUIElementPerformAction(el, "AXShowMenu")   # return code isn't evidence (core/ax README)
    menu, _ = ax.wait_until(open_menu_element, timeout=1.5)
    if menu is not None:
        return menu
    pt = ax.visible_point(el)
    if pt is None:
        raise StepAbort("its menu didn't open, and it isn't on screen to Control-click")
    log("    AXShowMenu opened nothing — Control-clicking it")
    ax.ctrl_click_at(*pt)
    menu, _ = ax.wait_until(open_menu_element, timeout=1.5)
    if menu is None:
        raise StepAbort("its menu didn't open")
    return menu


def _has_item(menu, hop: str) -> bool:
    return any((ax.title(it) or "").strip() == hop for it in ax.children(menu))


def run_context_menu(step: dict, log, stop_event=None) -> None:
    on, path, alt = step["on"], step["path"], step.get("alt") or []
    named = f" {step['target']!r}" if step.get("target") else ""
    log(f"  context menu ({on}{named}): {' > '.join(path)}" + (f"  (or {' > '.join(alt)})" if alt else ""))
    check_stop(stop_event)
    app = ax.app_element()
    mw = ax.main_window(app)
    if mw is None:
        raise StepAbort("Logic's project window isn't on this desktop — bring Logic to this desktop and try again")
    try:
        target = _targets(mw, on, step.get("target"))
    except ax.AxError as exc:
        raise StepAbort(str(exc)) from exc
    log(f"    target: {ax.region_name(target) if on == 'region' else ax.desc(target)!r}")
    t0 = time.monotonic()
    menu = open_context_menu(target, log)
    log(f"    menu open ({time.monotonic() - t0:.2f}s)")
    check_stop(stop_event)
    # Match the first hop exactly before pressing anything: the top block of this
    # menu reorders, so a loose match could press a neighbour.
    use = path if _has_item(menu, path[0]) else alt if alt and _has_item(menu, alt[0]) else None
    if use is None:
        ax.dismiss_menus(app)
        wait_menus_gone(timeout=1.0)
        raise StepAbort(f"{path[-1]!r} isn't in the {on}'s menu")
    if use is alt:
        log(f"    {path[0]!r} not in the menu — using {' > '.join(alt)}")
    try:
        ax.drill(menu, use)
    except ax.AxError as exc:
        ax.dismiss_menus(app)
        raise StepAbort(str(exc)) from exc
    if not wait_menus_gone(timeout=VERIFY_TIMEOUT_S):
        raise StepAbort(f"the menu stayed open after {use[-1]!r}")
    opens = step.get("opens")
    if opens:
        got, dt = ax.wait_until(lambda: ax.sheet_titled(mw, opens), timeout=4.0)
        if got is None:
            raise StepAbort(f"{opens!r} didn't open")
        log(f"    verify: {opens!r} sheet is open ({dt:.2f}s)")
