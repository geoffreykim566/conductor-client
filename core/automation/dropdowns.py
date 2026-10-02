"""The `choose` step: pick an option in the dropdown the previous click opened."""
import re
import time

from core import ax
from core.automation.errors import StepAbort
from core.automation.logic_focus import require_logic_frontmost
from core.automation.menus import wait_menu_count, wait_menus_gone
from core.automation.ocr_find import find_text, value_blob_right_of
from core.automation.timing import ACTION_SETTLE_S, VERIFY_INTERVAL_S, VERIFY_TIMEOUT_S
from core.events.keyboard import NAMED_KEYS, post_key, type_select


# Where the last click_text/click_value_of landed and the value it showed --
# what a following choose step finds its dropdown (and current value) by.
last_click: dict = {}


def _num_in(text: str) -> float | None:
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
    try:
        app = ax.app_element()
    except ax.AxError:
        return None, None
    menu, _ = ax.wait_until(lambda: ax.current_menu(app, last_click.get("point")), timeout=1.5)
    if menu is None:
        return None, None
    items = [it for it in ax.children(menu)
             if ax.title(it) and ax.ax_get(it, "AXEnabled") is not False]
    checked = next((i for i, it in enumerate(items) if ax.ax_get(it, "AXMenuItemMarkChar")), None)
    if checked is None and last_click.get("shown"):
        titles = [ax.title(it) for it in items]
        checked = _option_index(_title_for(last_click["shown"], shows), titles)
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
            hit = find_text([row], include_menus=False)
            blob = value_blob_right_of(hit["box"], hit["words"]) if hit else None
            shown = blob["label"] if blob else None
        else:
            # the control shows "Slicing" for the menu's "Flex Time - Slicing"
            texts = [want] + ([want.split(" - ", 1)[1]] if " - " in want else [])
            hit = find_text(texts, include_menus=False)
            shown = hit["text"] if hit else None
        if shown is not None and (_exact_option if exact else _same_option)(want, _title_for(shown, shows)):
            return shown
        time.sleep(VERIFY_INTERVAL_S)
    return shown


def run_choose(step: dict, choose_override: str | None, log, stop_event=None):
    value = step.get("value") or choose_override
    if not wait_menu_count(1):
        if step.get("optional"):
            log("  choose: no dropdown appeared (click may have selected "
                "directly) — skipping")
            return None
        raise StepAbort("choose: dropdown did not open")
    if value is None:
        log("  choose: no value given — Escape out (rerun with --choose=... "
            "to actually select)")
        require_logic_frontmost()
        post_key(NAMED_KEYS["escape"], stop_event=stop_event)
        wait_menus_gone()
        return None
    log(f"  choose: {value}")
    require_logic_frontmost()
    shows = step.get("shows") or {}
    items, checked = _popup_items(log, shows)
    relative = value.lower() in ("larger", "smaller")

    def close(msg: str):
        post_key(NAMED_KEYS["escape"], stop_event=stop_event)
        wait_menus_gone()
        log(f"    {msg}")

    if items is None:
        if relative:
            close("dropdown not readable via AX — Escaped")
            raise StepAbort(f"choose {value!r}: couldn't read the dropdown's options")
        # Absolute value, menu invisible to AX: type-select, verified by read-back.
        type_select(value, stop_event)
        time.sleep(ACTION_SETTLE_S)
        post_key(NAMED_KEYS["return"], stop_event=stop_event)
        prev, target = _title_for(last_click.get("shown"), shows), value
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
        prev = ax.title(items[checked]) if checked is not None else _title_for(last_click.get("shown"), shows)
        target = ax.title(items[idx])
        if idx == checked:
            close(f"already set to {target} — nothing to change")
            return None
        ax.ax_press(items[idx])
    if not wait_menus_gone():
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
        return None   # nothing to go back through / to (the choose_override path)

    return {"kind": "setting_chosen", "label": f"{step.get('row') or 'setting'} back to {prev}",
            "prev": prev, "row": step.get("row"), "reopen": step["reopen"], "shows": shows}
