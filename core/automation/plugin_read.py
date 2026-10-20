"""Read every value of a plugin through its Controls view, for the server's read_plugin_values.

Opens the plugin's window if it's closed, flips to Controls, reads each row's readout, then
puts the window back as it was. When Controls shows only 0-1 positions (some third-party
plug-ins), the values are OCR'd off the editor instead. Returns the request's `plugin_values`
shape: {plugin, track, values: {label: readout}} or {error}. Never raises: a failed read is an
answer Sol can give.
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from core import ax
from core.automation import editor_ocr
from core.automation.logic_focus import activate_logic, wait_logic_on_screen

MAX_ROWS = 100   # the server's cap (MAX_PLUGIN_VALUE_ROWS)


def read_plugin_values(plugin: str, track: str | None = None, log=print) -> dict:
    try:
        return _read(plugin, track, log)
    except Exception as exc:  # noqa: BLE001
        log(f"[plugin_read] {plugin!r} failed: {type(exc).__name__}: {exc}")
        return {"error": f"couldn't read {plugin}: {exc}"}


def _read(plugin: str, track: str | None, log) -> dict:
    if not activate_logic():
        return {"error": "Logic Pro couldn't be brought to the front"}
    wait_logic_on_screen()
    app = ax.app_element()
    mw = ax.main_window(app)
    if mw is None:
        return {"error": "Logic's project window isn't on this desktop"}
    if track and not ax.select_track(mw, track):
        return {"error": f"track {track!r} not found"}
    win = ax.plugin_window_for(app, plugin, track=track) if track else ax.plugin_window_for(app, plugin)
    opened = win is None
    if opened:
        win = ax.open_loaded_plugin(app, mw, plugin, track=track)
        if win is None:
            return {"error": f"{plugin} isn't on the selected track"}
    ax.ensure_on_screen(win)
    view_before = ax.current_view(win)
    try:
        if not ax.set_view(app, win, "Controls"):
            return {"error": f"couldn't switch {plugin} to Controls view"}
        rows = ax.param_rows(win)
        values = {label: ax.row_readout(ctl, ro) for label, (_, ctl, ro) in list(rows.items())[:MAX_ROWS]}
        name = ax.window_plugin_name(win) or plugin
        shown_track = ax.title(win) or track
        source = "controls"
        if ax.all_unitless(values.values()):
            source = "editor OCR"
            if not ax.set_view(app, win, "Editor"):
                return {"error": f"{plugin} shows its settings only as 0-1 positions, and its editor couldn't be opened"}
            knobs, why = editor_ocr.ocr_knobs(win)
            if not knobs:
                return {"error": f"{plugin} shows its settings only as 0-1 positions, and {why}, "
                                 f"so its exact settings can't be read"}
            values = {k["name"]: k["value"] for k in knobs[:MAX_ROWS]}
    finally:
        ax.set_view(app, win, "Controls" if view_before == "Controls" else "Editor")
        if opened:
            ax.close_window(win)
    log(f"[plugin_read] {name!r} on {shown_track!r}: {len(values)} rows from {source} "
        f"(opened={opened}, view was {view_before!r})")
    if not values:
        return {"error": f"{plugin} showed no readable controls"}
    return {"plugin": name, "track": shown_track, "values": values}


class PluginReadThread(QThread):
    """Runs read_plugin_values off the UI thread; `finished_read(dict)` carries the result."""
    finished_read = Signal(object)

    def __init__(self, plugin: str, track: str | None, parent=None) -> None:
        super().__init__(parent)
        self._plugin, self._track = plugin, track

    def run(self) -> None:
        self.finished_read.emit(read_plugin_values(self._plugin, self._track))
