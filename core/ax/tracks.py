"""Find and select a track by name in the Tracks area."""
from __future__ import annotations

import ApplicationServices as AS

from core.ax.channel_strip import selected_strip, strip
from core.ax.mouse import click_at
from core.ax.primitives import center, children, desc, wait_until
from core.ax.search import find_anywhere, find_child


def track_header(mw, name: str):
    hdr = find_anywhere(mw, desc_="Tracks header", role_="AXGroup")
    for h in (children(hdr) if hdr is not None else []):
        if f"\u201c{name}\u201d" in (desc(h) or "") or (desc(h) or "").endswith(f'"{name}"'):
            return h
    return None


def select_track(mw, name: str) -> bool:
    """Click the track header's name field so the Inspector shows that strip.
    Verified by the selected strip's description."""
    if strip(mw, name) is not None and selected_strip(mw) is not None and desc(selected_strip(mw)) == name:
        return True
    h = track_header(mw, name)
    if h is None:
        return False
    target = find_child(h, AS.kAXDescriptionAttribute, name, "AXTextField") or h
    c = center(target)
    if c is None:
        return False
    click_at(*c)
    got, _ = wait_until(lambda: (desc(selected_strip(mw)) == name) or None, timeout=3.0)
    return bool(got)
