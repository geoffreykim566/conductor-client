"""Read the current macOS Accessibility (AX) state of Logic Pro's on-screen
windows/dialogs as text, for live per-turn context alongside screenshots.

Passive only -- reads whatever's already open, no menu presses, no clicks,
no navigation. Mirrors capture/window_capture.py's pattern: pushed silently
every turn (see core/net/llm_client.py), fails soft to None on any error (Logic not
running, Accessibility permission not granted, an AX call failing) -- never
raises, this is best-effort context and must never block a turn.
"""
import ApplicationServices as AS
from AppKit import NSWorkspace

from config import LOGIC_PRO_APP_NAMES

# Bounds on the walk so a deeply nested window (or Logic itself) can't blow
# up capture time or the text payload sent to the server.
#
# Depth is a sanity ceiling only (track-header Mute/Solo sit at depth 8; see
# README "AX state capture depth"). Each node is one synchronous round trip
# into Logic (~0.5 ms), so the node budget bounds capture time; the char cap
# bounds the prompt payload.
_MAX_DEPTH = 20
_MAX_CHILDREN = 200
_MAX_NODES_PER_WINDOW = 2000
_MAX_CHARS = 12_000

# Pure chrome that carries no state worth a line (a slider's thumb, Logic's
# per-strip library badge) -- skipped so the char cap buys real content.
_SKIP_ROLES = {"AXValueIndicator"}
_SKIP_DESC_PREFIXES = ("library indicator",)


def _ax_get(el, attr):
    err, v = AS.AXUIElementCopyAttributeValue(el, attr, None)
    return v if err == 0 else None


def _find_pid() -> int | None:
    for a in NSWorkspace.sharedWorkspace().runningApplications():
        if str(a.localizedName()) in LOGIC_PRO_APP_NAMES:
            return a.processIdentifier()
    return None


def _ordered_children(el) -> list:
    """Children in tree order, except a child described as 'Tracks' is moved
    to the front. In the main project window the Inspector group precedes the
    Tracks group, and a big project's channel strips would otherwise consume
    the node/char budget before the per-track header rows (name, Mute, Solo)
    are reached. Harmless elsewhere: no other window has a 'Tracks' child.
    """
    kids = list(_ax_get(el, AS.kAXChildrenAttribute) or [])[:_MAX_CHILDREN]
    if len(kids) < 2:
        return kids
    first, rest = [], []
    for c in kids:
        (first if _ax_get(c, AS.kAXDescriptionAttribute) == "Tracks" else rest).append(c)
    return first + rest


def _describe(el, depth: int, lines: list[str], budget: list[int]) -> None:
    if budget[0] <= 0 or depth > _MAX_DEPTH:
        return
    role = _ax_get(el, AS.kAXRoleAttribute)
    # Neither node carries project state, and a wedged AX server returns the
    # app element as its own child (see README "Wedged AX server") -- stop at both.
    if role in ("AXApplication", "AXMenuBar"):
        return
    title = _ax_get(el, AS.kAXTitleAttribute)
    desc = _ax_get(el, AS.kAXDescriptionAttribute)
    value = _ax_get(el, AS.kAXValueAttribute)
    bits = [str(role or "?")]
    if title:
        bits.append(f"title={title!r}")
    if desc and desc != title:
        bits.append(f"desc={desc!r}")
    if value not in (None, ""):
        bits.append(f"value={value!r}")
    skip = role in _SKIP_ROLES or (
        isinstance(desc, str) and desc.startswith(_SKIP_DESC_PREFIXES)
    )
    # Pure structural nodes (no title/desc/value) aren't worth a line, but
    # still recurse into their children -- the useful state is often a few
    # hops below a plain AXGroup/AXSplitGroup wrapper.
    if len(bits) > 1 and not skip:
        lines.append("  " * depth + "- " + " ".join(bits))
        budget[0] -= 1

    for c in _ordered_children(el):
        _describe(c, depth + 1, lines, budget)


def capture_ax_state() -> str | None:
    """Text dump of every currently-open Logic Pro window/dialog/popup's AX
    state (roles, titles, values). None if Logic isn't running, Accessibility
    permission isn't granted, or nothing readable is found -- all of that
    collapses to the same "no AX context this turn" outcome for the caller.
    """
    try:
        pid = _find_pid()
        if pid is None:
            return None
        app = AS.AXUIElementCreateApplication(pid)
        windows = [
            w for w in (_ax_get(app, AS.kAXWindowsAttribute) or [])
            if _ax_get(w, AS.kAXRoleAttribute) != "AXApplication"  # see _describe
        ]
        if not windows:
            return None

        sections = []
        for w in windows:
            title = _ax_get(w, AS.kAXTitleAttribute) or "(untitled window)"
            lines: list[str] = []
            _describe(w, 0, lines, [_MAX_NODES_PER_WINDOW])
            if lines:
                sections.append(f"### {title}\n" + "\n".join(lines))

        if not sections:
            return None
        text = "\n\n".join(sections)
        if len(text) > _MAX_CHARS:
            text = text[:_MAX_CHARS] + "\n... (truncated)"
        return text
    except Exception:
        return None
