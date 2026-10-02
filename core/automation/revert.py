"""Undo a run's ledger, latest entry first (the walkthrough card's Revert).

Only the most recent run's ledger is kept by the UI (no rewind).
"""
from __future__ import annotations

import time

import ApplicationServices as AS

from core import ax
from core.automation.ax_steps import LEDGER_KIND_PARAM, LEDGER_KIND_PLUGIN, LEDGER_KIND_SETTING
from core.automation.errors import StepAbort
from core.automation.ocr_find import find_text, is_front_window
from core.automation.runner import run_steps
from core.automation.wire import wire_to_steps


def revert(ledger: list[dict], log=print) -> list[tuple[dict, bool, str]]:
    """Undo a run's ledger, latest entry first. Never raises; reports per entry."""
    results = []
    app = ax.app_element()
    mw = ax.main_window(app)
    for entry in reversed(ledger):
        try:
            if entry["kind"] in (LEDGER_KIND_PARAM, LEDGER_KIND_PLUGIN):
                _select_entry_track(mw, entry)
            if entry["kind"] == LEDGER_KIND_PARAM:
                track = entry.get("track")
                win = ax.plugin_window_for(app, entry["plugin"], track=track)
                reopened = win is None
                if reopened:
                    win = ax.open_loaded_plugin(app, mw, entry["plugin"], track=track)
                    if win is None:
                        raise ax.AxError(f"{entry['plugin']} isn't loaded on {track or 'the selected track'}")
                if entry.get("via") == "editor_checkbox":
                    _, cb = ax.editor_checkbox(win, entry["param"])
                    ax.set_editor_checkbox(cb, bool(entry["raw_before"]))
                    results.append((entry, True, f"{entry['param']} restored"))
                elif entry.get("via") == "editor":
                    ax.raise_window(win); ax.ensure_on_screen(win)
                    t = entry.get("text_before")
                    r = ax.type_param_value(app, win, entry["param"], str(ax.num(t) if t else entry["raw_before"])) if t else None
                    if r is None or r["raw"] != entry["raw_before"]:
                        ax.set_view(app, win, "Controls")
                        ax.write_param_raw(win, entry["param"], float(entry["raw_before"]))
                        ax.set_view(app, win, "Editor")
                    results.append((entry, True, f"{entry['param']} restored"))
                else:
                    ax.set_view(app, win, "Controls")
                    if entry.get("bool"):
                        got = ax.write_param_bool(win, entry["param"], "on" if entry["raw_before"] else "off")
                    else:
                        got = ax.write_param_raw(win, entry["param"], float(entry["raw_before"]))
                    ax.set_view(app, win, "Editor")
                    results.append((entry, True, f"{entry['param']} -> {got['readout']}"))
                # A band the run switched on to reach its slider goes back off,
                # whichever path wrote the value (editor view by now).
                if entry.get("enabled_band"):
                    _, cb = ax.editor_checkbox(win, entry["enabled_band"])
                    if cb is not None:
                        ax.set_editor_checkbox(cb, False)
                if reopened:
                    _close_window(win)
            elif entry["kind"] == LEDGER_KIND_PLUGIN:
                win = ax.plugin_window_for(app, entry["plugin"], track=entry.get("track"))
                if win is not None:
                    _close_window(win)
                ok = ax.remove_plugin(app, mw, entry["slot"], index=entry.get("index"))
                if not ok:
                    raise ax.AxError("slot menu removal failed")
                results.append((entry, True, f"removed {entry['plugin']}"))
            elif entry["kind"] == LEDGER_KIND_SETTING:
                _revert_setting(entry)
                results.append((entry, True, f"{entry.get('row') or 'setting'} back to {entry['prev']}"))
            else:
                results.append((entry, False, f"no inverse for {entry['kind']}"))
        except Exception as exc:  # noqa: BLE001
            results.append((entry, False, f"{type(exc).__name__}: {exc}"))
        msg = results[-1][2]
        log(f"[revert] {msg}" if msg == entry["label"] else f"[revert] {entry['label']}: {msg}")
        time.sleep(0.2)
    return results


def _select_entry_track(mw, entry: dict) -> None:
    track = entry.get("track")
    if track and not ax.select_track(mw, track):
        raise ax.AxError(f"track {track!r} not found in the Tracks area")


def _close_window(win) -> None:
    btn = ax.find_child(win, AS.kAXSubroleAttribute, "AXCloseButton") or \
        ax.find_child(win, AS.kAXDescriptionAttribute, "close", "AXButton")
    if btn is not None:
        ax.ax_press(btn)
        time.sleep(0.3)


def _revert_setting(entry: dict) -> None:
    """Pick the old value in the same dropdown again. Try the dropdown's own
    click first (its pane is usually still open); only if that isn't on
    screen in Logic's front window, replay the whole route -- some routes
    start with a toggle shortcut (flex's Cmd+F) that would hide what's
    already showing. A pane under another window (Settings over Project
    Settings) would take the short path's click itself."""

    route = wire_to_steps(entry["reopen"])
    pick = {"kind": "choose", "value": entry["prev"], "row": entry.get("row"), "shows": entry.get("shows")}
    log = lambda m: print(f"[revert] {m}")  # noqa: E731
    last = route[-1]
    texts = [last["label"]] if last["kind"] == "click_value_of" else (
        last["value"] if isinstance(last["value"], list) else [last["value"]])
    hit = find_text(texts, include_menus=False)
    if hit is not None and is_front_window(hit["win"]):
        try:
            run_steps([last, pick], log=log)
            return
        except StepAbort:
            pass
    elif hit is not None:
        log(f"{hit['text']!r} is showing but its window isn't in front — replaying the route")
    run_steps(route + [pick], log=log)
