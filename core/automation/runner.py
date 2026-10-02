"""Run a translated step list, one act->verify contract per step.

Step kinds: key, menu, click_text, click_value_of, choose (see README
"Step kinds") plus ax_open_plugin / ax_set_param (ax_steps.py). Any step may
carry `expect` (text that must appear after acting, else abort) and `final`
(the state-changing step). Every event batch is preceded by a frontmost
check, so a path aborts rather than typing into another app.
"""
import time

from core.automation.ax_steps import run_ax_open_plugin, run_ax_set_param, with_track
from core.automation.dropdowns import last_click, run_choose
from core.automation.errors import StepAbort
from core.automation.logic_focus import require_logic_frontmost
from core.automation.menus import menu_window_count, open_menubar_menu, wait_menu_count, wait_menus_gone
from core.automation.ocr_find import box_center_screen, find_text, is_front_window, value_blob_right_of, wait_for_text
from core.automation.timing import ACTION_SETTLE_S, MENU_SETTLE_S
from core.events.keyboard import NAMED_KEYS, post_key, press, type_select
from core.events.mouse import click_at
from core.events.stop import Stopped, check_stop


def _verify_expect(step: dict, log) -> None:
    expect = step.get("expect")
    if not expect:
        log("    verify: none declared — check manually")
        return
    hit = wait_for_text(expect)
    if hit is None:
        raise StepAbort(f"expected one of {expect!r} on screen; not found")
    name = hit["win"].get("kCGWindowName", "") or f"#{hit['win']['kCGWindowNumber']}"
    log(f"    verify: found {hit['text']!r} in window {name!r}")


def _cleanup_after_interrupt(log, max_presses: int = 6) -> None:
    """Close any menu(s) left open by a mid-hop interrupt — same Escape +
    wait_menus_gone() pattern run_choose() already uses to escape out of a
    dropdown, looped since a multi-hop path can leave more than one level
    open. Escape presses are tagged synthetic like everything else post_key
    posts, so this doesn't re-trigger the interrupt tap on itself."""
    for _ in range(max_presses):
        if menu_window_count() == 0:
            return
        post_key(NAMED_KEYS["escape"])
        wait_menus_gone(timeout=0.5)
    log(f"    interrupt cleanup: menus still open after {max_presses} Escape presses")


def _run_key(step: dict, log, stop_event=None) -> None:
    log(f"  key: {step['value']}")
    require_logic_frontmost()
    # Many view shortcuts toggle (Cmd+F Show Flex, Option+T): if what this
    # step exists to reveal is already on screen, pressing would hide it.
    expect = step.get("expect")
    if expect:
        hit = find_text(expect, include_menus=False)
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
    require_logic_frontmost()
    # The pane is already open: the row this route leads to is on screen in
    # Logic's front window -- reopening it is ~3 s of menu travel for nothing.
    # Keyed on the row label only, never a tab name ("Audio" stays visible
    # whichever Settings tab is showing).
    row = step.get("skip_if_row")
    if row:
        hit = find_text(row, include_menus=False)
        if hit is not None and is_front_window(hit["win"]):
            log(f"    already showing {hit['text']!r} — skipped the menu")
            return
        if hit is not None:
            log(f"    {hit['text']!r} is showing but its window isn't in front — opening it by menu")

    open_menubar_menu(path[0], stop_event)          # click the menu-bar title
    log(f"    open: {path[0]}")
    time.sleep(MENU_SETTLE_S)

    for hop in path[1:-1]:
        check_stop(stop_event)
        type_select(hop, stop_event)
        time.sleep(ACTION_SETTLE_S)
        count = menu_window_count()
        post_key(NAMED_KEYS["right"], stop_event=stop_event)  # enter the submenu
        if not wait_menu_count(count + 1):
            raise StepAbort(f"submenu {hop!r} did not open")
        log(f"    open: {hop}")
        time.sleep(MENU_SETTLE_S)

    check_stop(stop_event)
    type_select(path[-1], stop_event)
    time.sleep(ACTION_SETTLE_S)
    if step.get("final"):
        log(f"    activate (final): {path[-1]}")
    post_key(NAMED_KEYS["return"], stop_event=stop_event)
    wait_menus_gone()
    _verify_expect(step, log)


def _run_click(step: dict, log, stop_event=None) -> None:
    # A disclosure click toggles (Region Inspector's "Region"): if what it
    # reveals is already showing, clicking would collapse it -- same rule as
    # _run_key.
    expect = step.get("expect")
    if step["kind"] == "click_text" and expect:
        hit = find_text(expect, include_menus=False)
        if hit is not None:
            log(f"  click_text: {step['value']!r} — already showing {hit['text']!r}, skipped (it would toggle off)")
            return
    if step["kind"] == "click_text":
        texts = step["value"] if isinstance(step["value"], list) else [step["value"]]
        hit = wait_for_text(texts)
        if hit is None:
            raise StepAbort(f"click_text: none of {texts!r} found on screen")
        box = hit["box"]
        found = hit["text"]
    else:  # click_value_of
        hit = wait_for_text([step["label"]], include_menus=False)
        if hit is None:
            raise StepAbort(f"click_value_of: label {step['label']!r} not found")
        box = value_blob_right_of(hit["box"], hit["words"])
        if box is None:
            raise StepAbort(
                f"click_value_of: no value text right of {step['label']!r} "
                f"(row OCR gap?)")
        found = f"{step['label']} -> {box['label']!r}"

    x, y = box_center_screen(box, hit["img"].size, hit["win"])
    name = hit["win"].get("kCGWindowName", "") or f"#{hit['win']['kCGWindowNumber']}"
    log(f"  {step['kind']}: {found} in window {name!r} -> click ({x:.0f}, {y:.0f})")
    require_logic_frontmost()
    last_click.update(point=(x, y), shown=box.get("label") if step["kind"] == "click_value_of" else hit["text"])
    click_at(x, y, stop_event)
    time.sleep(ACTION_SETTLE_S)
    _verify_expect(step, log)


_HANDLERS = {
    "key": lambda step, opts, log, stop_event: _run_key(step, log, stop_event),
    "menu": lambda step, opts, log, stop_event: _run_menu(step, log, stop_event),
    "click_text": lambda step, opts, log, stop_event: _run_click(step, log, stop_event),
    "click_value_of": lambda step, opts, log, stop_event: _run_click(step, log, stop_event),
    "choose": lambda step, opts, log, stop_event: run_choose(step, opts.get("choose"), log, stop_event),
    "ax_open_plugin": lambda step, opts, log, stop_event: with_track(run_ax_open_plugin(step, log, stop_event)),
    "ax_set_param": lambda step, opts, log, stop_event: with_track(run_ax_set_param(step, log, stop_event)),
}


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
        if kind != "choose" and menu_window_count() > 0:
            # Nothing should be open between steps: an open menu or dropdown
            # swallows every keystroke the next step posts (see README
            # "Leftover menus"). Only a choose step expects one.

            log("  a menu was left open — closing it first")
            _cleanup_after_interrupt(log)
        try:
            entry = handler(step, opts, log, stop_event)
        except Stopped:
            log("  interrupted — closing any open menus")
            _cleanup_after_interrupt(log)
            return ledger
        if isinstance(entry, dict):
            ledger.append(entry)
        log(f"    ({time.monotonic() - t0:.2f}s)")

    return ledger
