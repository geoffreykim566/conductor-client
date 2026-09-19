"""AX step handlers + the revert ledger for core.executor.

Step kinds (wire key -> native kind):
  {"ax_open_plugin": "<name>"}                       -> ax_open_plugin
  {"ax_set_param": {"plugin": ..., "param": ..., "value": <display number>}}
                                                     -> ax_set_param

Each handler returns a ledger entry describing how to undo what it did:
  {"kind": ..., "label": <human text>, "inverse": <callable-name>, ...data}
`revert(ledger)` applies inverses latest-first and returns per-entry results.
Only the most recent run's ledger is kept by the UI (no rewind).
"""
from __future__ import annotations

import time

from core import ax_actions as ax
from core.executor import StepAbort, _check_stop

LEDGER_KIND_PLUGIN = "plugin_opened"
LEDGER_KIND_PARAM = "param_written"


def _mw_or_abort(app):
    mw = ax.main_window(app)
    if mw is None:
        raise StepAbort("Logic's main Tracks window not found")
    return mw


def run_ax_open_plugin(step: dict, log, stop_event=None) -> dict:
    name = step["value"]
    _check_stop(stop_event)
    app = ax.app_element()
    mw = _mw_or_abort(app)
    want_new = bool(step.get("new"))
    # Default: if the plugin is already on the selected track, open its window
    # rather than adding a second instance; add only when absent or explicitly asked.
    if not want_new and ax.loaded_slot(ax.selected_strip(mw), name) is not None:
        win = ax.open_loaded_plugin(app, mw, name)
        if win is None:
            raise StepAbort(f"{name!r} is loaded but its window couldn't be opened")
        ax.raise_window(win)
        log(f"    {name!r} already loaded — opened its window (no new instance)")
        return None   # nothing to revert
    try:
        slot_label, win, idx = ax.open_plugin_by_search(app, mw, name)
    except ax.AxError as exc:
        raise StepAbort(f"open plugin {name!r}: {exc}") from exc
    ax.raise_window(win)
    log(f"    added {name!r} (slot {idx}: {slot_label!r})")
    return {"kind": LEDGER_KIND_PLUGIN, "label": f"remove {name}", "plugin": name, "slot": slot_label, "index": idx}


def run_ax_set_param(step: dict, log, stop_event=None) -> dict:
    spec = step["value"]
    plugin, param, target = spec["plugin"], spec["param"], spec["value"]
    _check_stop(stop_event)
    app = ax.app_element()
    mw = _mw_or_abort(app)
    win = ax.plugin_window_for(app, plugin)
    opened_here = False
    if win is None:
        # the plugin is (presumably) loaded but its window is closed -- open it
        # via the slot's 'open' button; if it isn't loaded, that's a real miss
        s = ax.selected_strip(mw)
        g = next((g for g in ax.fx_slots(s)[1] if ax._norm(plugin)[:6] in ax._norm(ax.desc(g))), None)
        if g is None:
            raise StepAbort(f"plugin {plugin!r} is not loaded on the selected track")
        ax.ax_press(ax.find_child(g, ax.AS.kAXDescriptionAttribute, "open", "AXButton"))
        win, _ = ax.wait_until(lambda: ax.plugin_window_for(app, plugin), timeout=4.0)
        opened_here = True
        if win is None:
            raise StepAbort(f"couldn't open the {plugin!r} window")
    ax.raise_window(win)
    ax.ensure_on_screen(win)
    is_bool = isinstance(target, str) and target.strip().lower() in ax._ON + ax._OFF
    is_raw = isinstance(target, str) and target.startswith("raw:")
    # Preferred: stay in the editor view.
    #  (a) on/off targets -> the editor's own checkbox (band enables etc.)
    #  (b) numeric targets -> double-click the labelled slider, type the value.
    #      A disabled band's slider isn't interactive; enable it first (ledgered).
    if is_bool:
        k, cb = ax.editor_checkbox(win, param)
        if cb is not None:
            before = bool(ax.value(cb)); want = str(target).strip().lower() in ax._ON
            changed = ax.set_editor_checkbox(cb, want)
            log(f"    {plugin} / {k}: {'on' if before else 'off'} -> {'on' if want else 'off'} (editor checkbox)")
            if not changed:
                return None
            return {"kind": LEDGER_KIND_PARAM, "label": f"{k} back {'on' if before else 'off'}", "plugin": plugin,
                    "param": k, "raw_before": int(before), "bool": True, "via": "editor_checkbox",
                    "opened_window": opened_here}
    typed = None
    enabled_band = None
    if not (is_bool or is_raw):
        typed = ax.type_param_value(app, win, param, str(target))
        if typed is None:
            band = param.split()[0:2]   # 'Low Cut Frequency' -> 'Low Cut'
            k_cb, cb = ax.editor_checkbox(win, " ".join(band)) if band else (None, None)
            if cb is not None and not bool(ax.value(cb)):
                if ax.set_editor_checkbox(cb, True):
                    enabled_band = k_cb
                    log(f"    enabled {k_cb!r} band first")
                typed = ax.type_param_value(app, win, param, str(target))
    if typed is not None:
        log(f"    {plugin} / {typed['label']}: typed {target!r} (was {typed['text_before']!r}, raw {typed['raw_before']} -> {typed['raw']})")
        return {"kind": LEDGER_KIND_PARAM, "label": f"{typed['label']} back to {typed['text_before']}", "plugin": plugin,
                "param": typed["label"], "raw_before": typed["raw_before"], "text_before": typed["text_before"],
                "enabled_band": enabled_band, "via": "editor", "opened_window": opened_here}
    if not ax.set_view(app, win, "Controls"):
        raise StepAbort(f"couldn't switch {plugin!r} to Controls view")
    before = ax.read_param(win, param)
    if before is None:
        raise StepAbort(f"parameter {param!r} not found on {plugin!r}; available: "
                        f"{list(ax.param_rows(win))[:30]}")
    try:
        if before.get("kind") == "AXCheckBox" or (isinstance(target, str) and target.strip().lower() in ax._ON + ax._OFF):
            after = ax.write_param_bool(win, before["label"], target)
        elif isinstance(target, str) and target.startswith("raw:"):
            after = ax.write_param_raw(win, before["label"], float(target[4:]))
        else:
            after = ax.write_param_display(win, before["label"], float(target))
    except (ax.AxError, ValueError) as exc:
        raise StepAbort(f"set {param!r}: {exc}") from exc
    log(f"    {plugin} / {after['label']}: {before['readout']!r} -> {after['readout']!r} (raw {before['raw']} -> {after['raw']})")
    ax.set_view(app, win, "Editor")   # leave the plugin as the user expects to see it
    return {"kind": LEDGER_KIND_PARAM, "label": f"{after['label']} back to {before['readout']}",
            "plugin": plugin, "param": after["label"], "raw_before": before["raw"],
            "readout_before": before["readout"], "opened_window": opened_here,
            "bool": before.get("kind") == "AXCheckBox"}


def revert(ledger: list[dict], log=print) -> list[tuple[dict, bool, str]]:
    """Undo a run's ledger, latest entry first. Never raises; reports per entry."""
    results = []
    app = ax.app_element()
    mw = ax.main_window(app)
    for entry in reversed(ledger):
        try:
            if entry["kind"] == LEDGER_KIND_PARAM:
                win = ax.plugin_window_for(app, entry["plugin"])
                if win is None:
                    raise ax.AxError("plugin window not open")
                if entry.get("via") == "editor_checkbox":
                    _, cb = ax.editor_checkbox(win, entry["param"])
                    ax.set_editor_checkbox(cb, bool(entry["raw_before"]))
                    results.append((entry, True, f"{entry['param']} restored"))
                elif entry.get("via") == "editor":
                    ax.raise_window(win); ax.ensure_on_screen(win)
                    t = entry.get("text_before")
                    r = ax.type_param_value(app, win, entry["param"], str(ax._num(t) if t else entry["raw_before"])) if t else None
                    if r is None or r["raw"] != entry["raw_before"]:
                        ax.set_view(app, win, "Controls")
                        ax.write_param_raw(win, entry["param"], float(entry["raw_before"]))
                        ax.set_view(app, win, "Editor")
                    if entry.get("enabled_band"):
                        _, cb = ax.editor_checkbox(win, entry["enabled_band"])
                        if cb is not None:
                            ax.set_editor_checkbox(cb, False)
                    results.append((entry, True, f"{entry['param']} restored"))
                else:
                    ax.set_view(app, win, "Controls")
                    if entry.get("bool"):
                        got = ax.write_param_bool(win, entry["param"], "on" if entry["raw_before"] else "off")
                    else:
                        got = ax.write_param_raw(win, entry["param"], float(entry["raw_before"]))
                    ax.set_view(app, win, "Editor")
                    results.append((entry, True, f"{entry['param']} -> {got['readout']}"))
            elif entry["kind"] == LEDGER_KIND_PLUGIN:
                win = ax.plugin_window_for(app, entry["plugin"])
                if win is not None:
                    btn = ax.find_child(win, ax.AS.kAXSubroleAttribute, "AXCloseButton") or \
                        ax.find_child(win, ax.AS.kAXDescriptionAttribute, "close", "AXButton")
                    if btn is not None:
                        ax.ax_press(btn)
                        time.sleep(0.3)
                ok = ax.remove_plugin(app, mw, entry["slot"], index=entry.get("index"))
                if not ok:
                    raise ax.AxError("slot menu removal failed")
                results.append((entry, True, f"removed {entry['plugin']}"))
            else:
                results.append((entry, False, f"no inverse for {entry['kind']}"))
        except Exception as exc:  # noqa: BLE001
            results.append((entry, False, f"{type(exc).__name__}: {exc}"))
        log(f"[revert] {entry['label']}: {results[-1][2]}")
        time.sleep(0.2)
    return results


def register(handlers: dict) -> None:
    handlers["ax_open_plugin"] = lambda step, opts, log, stop_event: run_ax_open_plugin(step, log, stop_event)
    handlers["ax_set_param"] = lambda step, opts, log, stop_event: run_ax_set_param(step, log, stop_event)
