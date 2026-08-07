"""Locate pipeline (client-side): capture all plugin windows → OCR → match target.

Searches every open Logic plugin editor for the target control. OCR identity
(identify_plugin) tells us which plugin each window is; match_control finds the
control within it. One OCR pass serves both.

  resolve("threshold") -> {plugin, box, img, size, word_count, win_info}

box=None means no match (caller hides "Show me"). img is the best-res capture
of the matched window — used to render the in-bubble arrow without re-capturing.

Multiple windows matching the same target (e.g. "mix" with Valhalla + ChromaVerb
both open) are disambiguated via the optional element tiebreaker. If still
ambiguous, deny_reason="ambiguous" is set.

CLI (draws a debug PNG):
  cd server && PYTHONPATH=. ../client/.venv/bin/python ../client/core/locate.py threshold
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from core.matching import Box, _norm, identify_plugin, match_control
from core.ocr_vision import ocr_words
from core.window_capture import _capture_one_bestres, capture_all_plugin_windows

MIN_CONF = 40.0

_KEY_RE = re.compile(r"[^a-z0-9]+")


def _key(s: str) -> str:
    return _KEY_RE.sub("", s.lower())


def _build_plugin_map(plugin: str, img_w: int, img_h: int,
                      raw_map: dict) -> dict[str, Box]:
    """Compute a normalized control→Box dict for one plugin window.

    Fraction entries use the V12 chrome constants + the actual window size to
    turn (xfrac, yfrac) into a pixel box. Only 'fraction' type is handled here;
    'landmark_relative' and 'labeled' types are added as they're authored.
    """
    entries = raw_map.get("entries") or []
    chrome = raw_map.get("chrome") or {}
    top_px = chrome.get("top_px", 18)
    total_px = chrome.get("total_px", 81)

    result: dict[str, Box] = {}
    for entry in entries:
        if entry.get("plugin") != plugin:
            continue
        anchor_type = entry.get("anchor_type")
        anchor = entry.get("anchor") or {}
        key = _norm(entry.get("control", ""))
        if not key:
            continue

        if anchor_type == "fraction":
            xfrac = anchor.get("xfrac", 0.5)
            yfrac = anchor.get("yfrac", 0.5)
            cx = int(xfrac * img_w)
            cy = int(top_px + yfrac * (img_h - total_px))
            result[key] = {
                "left": cx - 10, "top": cy - 10,
                "width": 20, "height": 20,
                "conf": 100.0,
                "label": entry.get("control", key),
            }
    return result


def resolve(target: str, element: str | None = None,
            control_map: dict[str, Box] | None = None,
            raw_map: dict | None = None) -> dict:
    """Search all open plugin windows for target. Returns the matched window's data.

    element: optional tiebreaker plugin name when multiple windows match the same
    control (e.g. "mix" open in both Valhalla and ChromaVerb). Ignored otherwise.
    raw_map: {entries, chrome} from GET /v1/control-map. When provided, fraction-type
    entries are resolved per-window using the actual image dimensions.

    Return keys: plugin (str|None), box (Box|None), img (Image|None),
    size (tuple|None), word_count (int), win_info (dict|None),
    deny_reason (str, only on deny).
    """
    captures = capture_all_plugin_windows()
    if not captures:
        return {"plugin": None, "box": None, "img": None, "size": None,
                "word_count": 0, "deny_reason": "no_logic_windows"}

    hits: list[dict] = []
    for img, win_info in captures:
        words = ocr_words(img, MIN_CONF)
        if not words:
            img2 = _capture_one_bestres(win_info)
            if img2 is not None:
                words = ocr_words(img2, MIN_CONF)
                img = img2
        plugin = identify_plugin(words)
        # Build a plugin-specific map from raw_map fraction entries; fall back to
        # the static control_map arg (used by tests / CLI).
        cmap = control_map
        if raw_map and plugin:
            w, h = img.size
            built = _build_plugin_map(plugin, w, h, raw_map)
            if built:
                cmap = built
        box = match_control(target, words, cmap)
        if box is not None:
            hits.append({"plugin": plugin, "box": box, "img": img,
                         "size": img.size, "word_count": len(words),
                         "win_info": win_info})

    if not hits:
        return {"plugin": None, "box": None, "img": None, "size": None,
                "word_count": 0, "deny_reason": "not_found"}
    if len(hits) == 1:
        return hits[0]

    # Multiple windows matched — element breaks the tie
    if element:
        elem_key = _key(element)
        for hit in hits:
            if hit["plugin"] and _key(hit["plugin"]) == elem_key:
                return hit

    return {"plugin": None, "box": None, "img": None, "size": None,
            "word_count": 0, "deny_reason": "ambiguous",
            "candidates": [h["plugin"] for h in hits]}


def _main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(2)
    target = args[0]
    element = next((a[len("--element="):] for a in sys.argv[1:]
                    if a.startswith("--element=")), None)

    from PIL import ImageDraw

    result = resolve(target, element=element)
    plugin = result.get("plugin")
    box = result.get("box")
    img = result.get("img")
    print(f"target={target!r}  element={element!r}  plugin={plugin!r}  "
          f"ocr_words={result.get('word_count')}  size={result.get('size')}")
    if box is None:
        print(f"  no match ({result.get('deny_reason', 'unknown')}) → no Show me")
        return
    print(f"  box={box}")
    if img is not None:
        d = ImageDraw.Draw(img)
        x, y, w, h = box["left"], box["top"], box["width"], box["height"]
        d.rectangle([x, y, x + w, y + h], outline=(10, 132, 255), width=3)
        d.text((x, max(y - 14, 0)), box["label"], fill=(10, 132, 255))
        out = (pathlib.Path(__file__).resolve().parent.parent.parent
               / "server" / "diagnostics" / f"diag_locate_{target}.png")
        img.save(out)
        print(f"  saved {out.name}")


if __name__ == "__main__":
    _main()
