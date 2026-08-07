"""S2 matching layer: OCR words + a target term -> the control's pixel box.

Sits between tier-1 OCR (Apple Vision, `_ocr_vision.ocr_words`) and the "Show me"
overlay. OCR hands us a flat list of word boxes; the user's query gives a target
(`extract.element`). This module decides *which* box is the control — robustly,
because the naive `term in text` prototype (diag_pointer_ocr.py) breaks on:
  - multi-word labels OCR splits ("MAKE"+"UP")        -> recombine adjacent boxes
  - greedy substrings ("250" in "2500", "gain" x3)    -> whole-token matching
  - axis ticks / readouts at different rows            -> row clustering
  - non-control chrome ("Default", "dB", version)      -> stoplist

Pure functions, no I/O — runs client-side (OCR is macOS-local). Word dicts are the
`_ocr_vision.ocr_words` shape: {text, left, top, width, height, conf}, top-left
pixel origin.
"""
from __future__ import annotations

import re

OCRWord = dict   # {text, left, top, width, height, conf}
Box = dict       # {left, top, width, height, conf, label}

# Eventually sourced from the KB; hardcoded to the S3b-tested set for now.
KNOWN_PLUGINS = ("Compressor", "Channel EQ", "ChromaVerb", "Space Designer",
                 "Valhalla Supermassive")

# Chrome / units / non-control text OCR reads but never points to.
STOPLIST = {
    "default", "preset", "compare", "copy", "paste", "undo", "redo", "view",
    "db", "hz", "ms", "s", "khz", "k", "audio", "setting", "settings",
    # Plugin name-strip text — identity, not a control target
    "compressor", "channel eq", "chromaverb", "space designer", "valhalla supermassive",
}

_NORM = re.compile(r"[^a-z0-9 ]+")
_ROW_FRAC = 0.6   # words within 0.6*line-height share a row

# --- Confidence floor (S2 output) ---------------------------------------------
# A match must clear all three to earn a pointer (else deny / "no Show me").
# Pinned from the S3b probe set: true hits score 0 @ conf 100 with a unique
# winner; nearest wrong candidate scores 2; the `gain` case ties 3-way at 0.
# So uniqueness — not OCR conf — is the load-bearing signal here.
_MAX_SCORE = 1    # 0 exact / 1 single whole-token contain; >=2 = sloppy, reject
_MIN_CONF = 90.0  # OCR legibility sanity gate (Vision=100, tesseract=96-97)


def _norm(s: str) -> str:
    result = _NORM.sub("", s.lower()).strip()
    # Apple Vision reads "I/O" as "1/O"; after stripping "/" both sides leave
    # "io" (query) vs "1o" (OCR). Map "1o" → "io" so they agree.
    return result.replace("1o", "io")


def _rows(words: list[OCRWord]) -> list[list[OCRWord]]:
    """Cluster words into visual rows by vertical overlap, each sorted left->right."""
    rows: list[list[OCRWord]] = []
    for w in sorted(words, key=lambda w: w["top"]):
        placed = False
        for row in rows:
            ref = row[0]
            tol = max(ref["height"], w["height"]) * _ROW_FRAC
            if abs(w["top"] - ref["top"]) <= tol:
                row.append(w)
                placed = True
                break
        if not placed:
            rows.append([w])
    for row in rows:
        row.sort(key=lambda w: w["left"])
    return rows


def _clean_label(text: str) -> str:
    """Fix display artifacts in OCR'd control labels."""
    return text.replace("1/O", "I/O").rstrip(":").strip()


def _merge(words: list[OCRWord]) -> Box:
    """Bounding box over a run of adjacent words; conf = min, label = raw join."""
    left = min(w["left"] for w in words)
    top = min(w["top"] for w in words)
    right = max(w["left"] + w["width"] for w in words)
    bottom = max(w["top"] + w["height"] for w in words)
    return {
        "left": left, "top": top, "width": right - left, "height": bottom - top,
        "conf": min(w["conf"] for w in words),
        "label": _clean_label(" ".join(w["text"] for w in words)),
    }


def _candidates(words: list[OCRWord], max_gram: int = 3) -> list[tuple[Box, str]]:
    """Every 1..max_gram run of adjacent same-row words, as (box, normalized text)."""
    out: list[tuple[Box, str]] = []
    for row in _rows(words):
        for i in range(len(row)):
            for n in range(1, max_gram + 1):
                if i + n > len(row):
                    break
                run = row[i:i + n]
                norm = _norm(" ".join(w["text"] for w in run))
                if norm:
                    out.append((_merge(run), norm))
    return out


def _score(target: str, cand: str) -> int | None:
    """Lower = better. None = no match. Whole-token, not substring."""
    t_tokens, c_tokens = target.split(), cand.split()
    if cand == target or cand.replace(" ", "") == target.replace(" ", ""):
        return 0                                   # exact (incl. "make up"=="makeup")
    if t_tokens and all(tok in c_tokens for tok in t_tokens):
        return 1 + (len(c_tokens) - len(t_tokens)) # whole-token contains; fewer extras better
    return None


def match_control(target: str, words: list[OCRWord],
                  control_map: dict[str, Box] | None = None) -> Box | None:
    """Resolve `target` to a control box. OCR first, then the tier-2 control-map
    (D15, plugin-scoped by the caller) for textless controls, else None (caller
    hides "Show me")."""
    norm_target = _norm(target)
    if not norm_target:
        return None

    scored: list[tuple[int, float, int, Box]] = []
    for box, cand in _candidates(words):
        if cand in STOPLIST:
            continue
        s = _score(norm_target, cand)
        if s is not None:
            # rank: score, then highest conf, then leftmost (stable, explains ties)
            scored.append((s, -box["conf"], box["left"], box))
    if scored:
        scored.sort(key=lambda r: r[:3])
        best_score, _, _, best_box = scored[0]
        tied = sum(1 for r in scored if r[0] == best_score)
        # Confidence floor: clean match (1), a unique winner (2), legible read (3).
        # Ambiguous/weak/illegible -> fall through to tier-2, else deny. Never
        # tiebreak a real ambiguity (e.g. 3x "GAIN") into a confident wrong arrow.
        if best_score <= _MAX_SCORE and tied == 1 and best_box["conf"] >= _MIN_CONF:
            return best_box

    # Tier-2: textless control with a hardcoded map entry (e.g. EQ band handle).
    if control_map and norm_target in control_map:
        return control_map[norm_target]
    return None


def identify_plugin(words: list[OCRWord],
                    known: tuple[str, ...] = KNOWN_PLUGINS) -> str | None:
    """Match the rendered plugin-name strip (kCGWindowName is empty) against the
    known set. Prefers the bottom-most match — the name strip sits at the window
    foot. Returns the canonical plugin name, or None (unidentified -> no Show me)."""
    # Collapse spaces: OCR may split ("Channel" "EQ") or join ("ValhallaSupermassive").
    known_norm = {_norm(k).replace(" ", ""): k for k in known}
    best: tuple[float, str] | None = None   # (top, canonical) — keep the lowest strip
    for box, cand in _candidates(words):
        key = cand.replace(" ", "")
        if key in known_norm and (best is None or box["top"] > best[0]):
            best = (box["top"], known_norm[key])
    return best[1] if best else None
