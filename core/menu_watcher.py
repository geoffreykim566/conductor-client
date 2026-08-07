"""Menu-detection helpers: find Logic Pro popup menus and fuzzy-match items in them.

Pure functions only — `core.executor` calls these directly for its one-shot,
act-then-verify captures. (Earlier this module also held a stateful, per-step
MenuWatcher QThread, then `core.walkthrough_poller`'s continuous classification
loop; both are gone now that the executor drives Logic itself instead of
watching a human do it — see executor-build-log.md, 2026-07-13/14.)
"""
import re

import Quartz

from config import LOGIC_PRO_APP_NAMES


# ---------------------------------------------------------------------------
# Window helpers

def _find_logic_menu_windows() -> list[dict]:
    """Return all on-screen Logic Pro popup menu windows (layer 101)."""
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    return [
        w for w in window_list
        if w.get("kCGWindowLayer") == 101
        and w.get("kCGWindowOwnerName", "") in LOGIC_PRO_APP_NAMES
        and w.get("kCGWindowBounds", {}).get("Width", 0) > 20
        and w.get("kCGWindowBounds", {}).get("Height", 0) > 20
    ]


# ---------------------------------------------------------------------------
# Fuzzy matching

def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", s.lower())


def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[:]
        dp[0] = i
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[j] = prev[j - 1]
            else:
                dp[j] = 1 + min(prev[j], dp[j - 1], prev[j - 1])
    return dp[n]


def _tokens_match(target_toks: list[str], candidate_toks: list[str]) -> bool:
    if len(target_toks) != len(candidate_toks):
        return False
    for t, c in zip(target_toks, candidate_toks):
        c = c.rstrip("…").rstrip(".")  # tolerate "…" truncation
        if t == c:
            continue
        max_dist = 1 if len(t) <= 5 else 2
        if _edit_distance(t, c) > max_dist:
            return False
    return True


def _fuzzy_match_menu_item(target: str, words: list[dict]) -> dict | None:
    """Find `target` text in an OCR word list; return a bounding-box dict or None.

    Row-clusters words by y-proximity, then slides a token window along each row
    looking for a fuzzy match. Returns the union bounding box of the matched tokens.
    """
    target_toks = [_norm(t) for t in target.split() if _norm(t)]
    if not target_toks:
        return None

    sorted_words = sorted(words, key=lambda w: (w["top"], w["left"]))

    # Group into rows by y proximity (within 60% of word height)
    rows: list[list[dict]] = []
    for w in sorted_words:
        h = max(w["height"], 1)
        placed = False
        for row in rows:
            if abs(w["top"] - row[0]["top"]) < h * 0.6:
                row.append(w)
                placed = True
                break
        if not placed:
            rows.append([w])

    n = len(target_toks)
    exact_box = None
    partial_box = None
    for row in rows:
        # Rows accumulate in (top, left) sort order, but per-word OCR boxes on
        # one visual line can differ by a pixel of top — which then interleaves
        # tokens out of reading order ("Rate:" top=145 before "Sample" top=146,
        # so the row read ['rate','sample'] and 'Sample Rate' never matched).
        # Reading order within a row is left-to-right, unconditionally.
        row.sort(key=lambda w: w["left"])
        normed = [_norm(w["text"]) for w in row]
        # Drop empty tokens (punctuation-only); keep index mapping back to row
        indexed = [(i, t) for i, t in enumerate(normed) if t]
        idxs = [i for i, _ in indexed]
        toks = [t for _, t in indexed]

        for start in range(len(toks) - n + 1):
            if _tokens_match(target_toks, toks[start:start + n]):
                matched = [row[idxs[start + j]] for j in range(n)]
                left = min(w["left"] for w in matched)
                top = min(w["top"] for w in matched)
                right = max(w["left"] + w["width"] for w in matched)
                bottom = max(w["top"] + w["height"] for w in matched)
                box = {
                    "left": left,
                    "top": top,
                    "width": right - left,
                    "height": bottom - top,
                    "label": target,
                }
                # An exact row (the whole menu item is just the target, e.g.
                # "Control Surfaces") is preferred over a match that's only a
                # sub-span of a longer item (e.g. "...Control Surfaces" inside
                # "Bypass All Control Surfaces") — the shorter target is a
                # real substring of the longer label's text, not the item
                # itself, so it should never win over an exact hit elsewhere
                # on screen.
                if len(toks) == n:
                    if exact_box is None:
                        exact_box = box
                elif partial_box is None:
                    partial_box = box

    return exact_box if exact_box is not None else partial_box
