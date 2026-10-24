"""Regions in the Tracks area: find them, pick the one a region-menu step acts on."""
from __future__ import annotations

import re

from core.ax.primitives import AxError, ax_get, desc, frame, parent, role
from core.ax.search import find_all, find_anywhere


def regions(mw) -> list:
    """Every region element under Tracks contents (each track's row holds its regions)."""
    contents = find_anywhere(mw, desc_="Tracks contents")
    return find_all(contents, lambda e: role(e) == "AXLayoutItem" and ax_get(e, "AXRoleDescription") == "Region",
                    maxd=3) if contents is not None else []


def is_audio(region) -> bool:
    return "audio region" in (ax_get(region, "AXHelp") or "").lower()


def _key(name: str) -> str:
    """A region name as compared: Logic's ' (Audio)' and ', muted' dropped, letters and digits only."""
    name = re.sub(r",\s*muted$", "", (name or "").strip())
    name = re.sub(r"\s*\(Audio\)$", "", name)
    return re.sub(r"[^a-z0-9]", "", name.lower())


def pick_region(found: list[tuple], kind: str = "audio", name: str | None = None):
    """Pure pick over (element, selected, is_audio, name) tuples. A named region wins
    (exact name first, then the one name containing it), whatever is selected; else the
    first selected region, else the only one of `kind`. Raises AxError saying what to do."""
    pool = [f for f in found if f[2]] if kind == "audio" else found
    if name:
        key = _key(name)
        hits = [f for f in pool if _key(f[3]) == key] or [f for f in pool if key and key in _key(f[3])]
        if len(hits) == 1:
            return hits[0][0]
        if not hits:
            raise AxError(f"there's no {kind} region named {name!r}")
        raise AxError(f"more than one region matches {name!r}: {', '.join(f[3] for f in hits)}")
    selected = [f for f in found if f[1]]
    if selected:
        el, _, audio = selected[0][:3]
        if kind == "audio" and not audio:
            raise AxError("the selected region isn't an audio region")
        return el
    if len(pool) == 1:
        return pool[0][0]
    if not pool:
        raise AxError(f"there's no {kind} region in the project")
    raise AxError(f"select the {kind} region first")


def target_region(mw, kind: str = "audio", name: str | None = None):
    return pick_region([(r, ax_get(r, "AXSelected") is True, is_audio(r), desc(r) or "") for r in regions(mw)],
                       kind, name)


def visible_point(region):
    """A point inside the part of the region the Tracks area shows, or None when none of
    it is on screen. The region's frame runs past the view when it's scrolled or long."""
    f = frame(region)
    area = parent(region)
    while area is not None and role(area) != "AXScrollArea":
        area = parent(area)
    v = frame(area) if area is not None else None
    if f is None or v is None:
        return None
    x0, y0 = max(f[0], v[0]), max(f[1], v[1])
    x1, y1 = min(f[0] + f[2], v[0] + v[2]), min(f[1] + f[3], v[1] + v[3])
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    return (x0 + min(20, (x1 - x0) / 2), y0 + (y1 - y0) / 2)


def region_name(region) -> str:
    return desc(region) or ""

