"""AX step handlers (open a plugin, set a parameter); each returns a revert-ledger entry.

Wire key -> native kind:
  {"ax_open_plugin": "<name>"}                                        -> ax_open_plugin
  {"ax_set_param": {"plugin", "param", "value": <display number>}}    -> ax_set_param

A ledger entry is {"kind", "label": <human text>, ...undo data}; revert.py
applies them. A handler returns None when it changed nothing.
"""
from __future__ import annotations

import ApplicationServices as AS

from core import ax
from core.automation.errors import StepAbort
from core.events.stop import check_stop


LEDGER_KIND_PLUGIN = "plugin_opened"
LEDGER_KIND_PARAM = "param_written"
LEDGER_KIND_SETTING = "setting_chosen"   # written by dropdowns.run_choose


def _mw_or_abort(app):
    mw = ax.main_window(app)
    if mw is None:
        # Logic is running but exposes no windows: it's on another desktop/Space,
        # minimized, or the project is closed.

        raise StepAbort("Logic's project window isn't on this desktop — bring Logic Pro "
                        "to this desktop (or un-minimize it) and try again")
    return mw


def _select_track_if_named(mw, track: str | None, log) -> None:
    if not track:
        return
    if not ax.select_track(mw, track):
        raise StepAbort(f"track {track!r} not found in the Tracks area")
    log(f"    selected track {track!r}")


def run_ax_open_plugin(step: dict, log, stop_event=None) -> dict:
    name = step["value"]
    check_stop(stop_event)
    app = ax.app_element()
    mw = _mw_or_abort(app)
    _select_track_if_named(mw, step.get("track"), log)
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
    check_stop(stop_event)
    app = ax.app_element()
    mw = _mw_or_abort(app)
    _select_track_if_named(mw, spec.get("track"), log)
    win = ax.plugin_window_for(app, plugin)
    opened_here = False
    if win is None:
        # the plugin is (presumably) loaded but its window is closed -- open it
        # via the slot's 'open' button; if it isn't loaded, that's a real miss
        s = ax.selected_strip(mw)
        g = next((g for g in ax.fx_slots(s)[1] if ax.norm(plugin)[:6] in ax.norm(ax.desc(g))), None)
        if g is None:
            raise StepAbort(f"plugin {plugin!r} is not loaded on the selected track")
        ax.ax_press(ax.find_child(g, AS.kAXDescriptionAttribute, "open", "AXButton"))
        win, _ = ax.wait_until(lambda: ax.plugin_window_for(app, plugin), timeout=4.0)
        opened_here = True
        if win is None:
            raise StepAbort(f"couldn't open the {plugin!r} window")
    ax.raise_window(win)
    ax.ensure_on_screen(win)
    is_bool = isinstance(target, str) and target.strip().lower() in ax.ON + ax.OFF
    is_raw = isinstance(target, str) and target.startswith("raw:")
    # Preferred: stay in the editor view.
    #  (a) on/off targets -> the editor's own checkbox (band enables etc.)
    #  (b) numeric targets -> double-click the labelled slider, type the value.
    #      A disabled band's slider isn't interactive; enable it first (ledgered).
    if is_bool:
        k, cb = ax.editor_checkbox(win, param)
        if cb is not None:
            before = bool(ax.value(cb)); want = str(target).strip().lower() in ax.ON
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
        if before.get("kind") == "AXCheckBox" or (isinstance(target, str) and target.strip().lower() in ax.ON + ax.OFF):
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
            "bool": before.get("kind") == "AXCheckBox",
            "enabled_band": enabled_band}   # the editor path may have switched it on before falling back here


def with_track(entry: dict | None) -> dict | None:
    """Stamp a plugin/param ledger entry with the track it was made on (the
    selected strip after the step), so Revert can select it again -- the user
    may have selected another track since."""
    if isinstance(entry, dict) and "track" not in entry:
        mw = ax.main_window(ax.app_element())
        strip = ax.selected_strip(mw) if mw is not None else None
        entry["track"] = ax.desc(strip) if strip is not None else None
    return entry
