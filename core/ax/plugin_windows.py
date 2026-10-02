"""Identify which open Logic window shows which plugin."""
from __future__ import annotations

from core.ax.app import app_windows
from core.ax.primitives import children, norm, role, title, value


def plugin_windows_seen(app) -> set[tuple[str, str]]:
    """(window title, plugin shown) for every open window -- the 'before' set for
    plugin_window_for. Titles alone can't do this job: plugin windows are titled
    after the TRACK, so a second plugin on the same track opens a second window
    with an identical title. The pair also covers Logic reusing one window and
    swapping the plugin inside it."""

    return {(title(w) or "", window_plugin_name(w) or "") for w in app_windows(app)}


def plugin_window_for(app, name: str, before: set[tuple[str, str]] | None = None,
                      track: str | None = None):
    """Find the open plugin window for `name` (title = track name; identity = the
    titled editor AXGroup or the trailing AXStaticText). `before` is a set of
    (title, plugin) pairs from plugin_windows_seen: a window whose pair was
    already present is not the one this call just opened. `track` keeps only
    that track's windows (the same plugin can be open on two tracks)."""
    for w in app_windows(app):
        shown = window_plugin_name(w)
        if before is not None and (title(w) or "", shown or "") in before:
            continue
        if track is not None and (title(w) or "") != track:
            continue
        if shown and (norm(name) in norm(shown) or norm(shown) in norm(name)):
            return w
    return None


def window_plugin_name(w) -> str | None:
    """Plugin windows are titled after the track. Identity: the header's own
    plugin-name AXStaticText (a DIRECT child of the window, present in both
    Editor and Controls view), else the titled editor AXGroup (Editor view)."""
    direct = [value(c) for c in children(w) if role(c) == "AXStaticText" and value(c)]
    direct = [t for t in direct if t not in ("View:", title(w)) and not str(t).endswith(":")]
    if direct:
        return direct[-1]
    g = next((c for c in children(w) if role(c) == "AXGroup" and title(c)), None)
    return title(g) if g is not None else None
