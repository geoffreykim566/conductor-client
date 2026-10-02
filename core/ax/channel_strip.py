"""A track's channel strip in the Mixer/Inspector, and its audio-FX slots."""
from __future__ import annotations

import ApplicationServices as AS

from core.ax.primitives import children, desc, norm, role
from core.ax.search import find_anywhere, find_child


def strip(mw, track_name: str):
    mixer = find_anywhere(mw, desc_="Mixer", role_="AXLayoutArea")
    return find_child(mixer, AS.kAXDescriptionAttribute, track_name, "AXLayoutItem") if mixer else None


def selected_strip(mw):
    """The Inspector shows the selected track's strip first (before 'Stereo Out')."""
    mixer = find_anywhere(mw, desc_="Mixer", role_="AXLayoutArea")
    items = [c for c in children(mixer) if role(c) == "AXLayoutItem"] if mixer else []
    return items[0] if items else None


def _is_slot_group(c):
    return role(c) == "AXGroup" and {"bypass", "open", "list"} <= {desc(k) for k in children(c)}


def fx_slots(strip_el):
    empty = find_child(strip_el, AS.kAXDescriptionAttribute, "audio plug-in", "AXButton") if strip_el else None
    loaded = [c for c in children(strip_el) if _is_slot_group(c)] if strip_el else []
    return empty, loaded


def loaded_names(strip_el) -> list[str]:
    return [desc(g) or "" for g in fx_slots(strip_el)[1]]


def loaded_slot(strip_el, name: str, index: int | None = None):
    """The slot group for a loaded plugin, by index if given and it still holds
    that plugin, else by label prefix. The index is where the plugin landed when
    it was added; later adds and removals shift slots, so it's only a hint."""
    groups = fx_slots(strip_el)[1]
    key = norm(name)[:6]
    if index is not None and 0 <= index < len(groups) and norm(desc(groups[index])).startswith(key):
        return groups[index]
    return next((g for g in groups if norm(desc(g)).startswith(key)), None)
