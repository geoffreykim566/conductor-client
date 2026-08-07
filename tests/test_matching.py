"""S2 matching-layer tests, seeded with real OCR word-lists from the S3b sweep.

No pytest dependency (client venv lacks it) and no live Logic: fixtures are
subsets of the actual `diag_pointer_ocr.py` dumps captured 2026-06-21/22. Runs
under any Python:  python client/tests/test_matching.py
(pytest also discovers the test_* functions if it's ever added.)
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from core.locate import _build_plugin_map
from core.matching import identify_plugin, match_control


def w(text: str, left: int, top: int, conf: float = 100.0,
      width: int | None = None, height: int = 36) -> dict:
    """Build an OCRWord; width estimated from text length when unspecified."""
    return {"text": text, "left": left, "top": top,
            "width": width if width is not None else max(len(text) * 11, 12),
            "height": height, "conf": conf}


# --- real subsets of the sweep dumps (text@left,top) ---------------------------
COMPRESSOR = [
    w("Default", 76, 36), w("Compare", 152, 66),
    w("THRESHOLD", 150, 349), w("RATIO", 288, 349), w("MAKE", 402, 349), w("UP", 435, 349),
    w("AUTO", 484, 353), w("GAIN", 518, 353),
    w("INPUT", 18, 475), w("GAIN", 55, 475), w("KNEE", 168, 475), w("ATTACK", 284, 475),
    w("RELEASE", 400, 475), w("MIX", 616, 475), w("OUTPUT", 676, 475), w("GAIN", 724, 475),
    w("Compressor", 330, 600),
]
CHANNEL_EQ = [
    w("20.0", 139, 1006), w("75.0", 453, 1006), w("100", 775, 1006), w("250", 1088, 1005),
    w("1040", 1391, 1006), w("2500", 1705, 1006), w("7500", 2015, 1005), w("20000", 2316, 1005),
    w("2k", 1681, 640), w("8k", 2162, 640),  # axis ticks (different row)
    w("Analyzer", 123, 1193), w("Q-Couple", 397, 1196), w("HQ", 620, 1197),
    w("Channel", 1256, 1280), w("EQ", 1416, 1281),
]
VALHALLA = [
    w("MIX", 177, 458), w("DELAY", 573, 458), w("WARP", 957, 458), w("FEEDBACK", 1324, 448),
    w("WIDTH", 144, 775), w("DENSITY", 1356, 777),
    w("ValhallaSupermassive", 924, 1381),
]


def _check(name, got, ok):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"   got={got}"))
    return ok


def test_matching() -> bool:
    results = []

    # 1. multi-word label OCR split -> recombine ("MAKE"+"UP" matches "makeup")
    b = match_control("makeup", COMPRESSOR)
    results.append(_check("makeup -> MAKE UP", b, b and b["label"] == "MAKE UP"))

    # 2. "output" disambiguates to the OUTPUT control (left~676), not INPUT/AUTO gain
    b = match_control("output", COMPRESSOR)
    results.append(_check("output -> OUTPUT region", b, b and 660 <= b["left"] <= 740))

    # 3. greedy substring: "250" must NOT match "2500"
    b = match_control("250", CHANNEL_EQ)
    results.append(_check("250 != 2500", b, b and b["label"] == "250" and b["left"] == 1088))

    # 4. exact numeric readout
    b = match_control("7500", CHANNEL_EQ)
    results.append(_check("7500 -> readout", b, b and b["label"] == "7500"))

    # 5. textless control: no OCR text -> None, then tier-2 control-map hit
    b = match_control("high shelf", CHANNEL_EQ)
    results.append(_check("high shelf -> None (no text)", b, b is None))
    cmap = {"high shelf": {"left": 2000, "top": 700, "width": 20, "height": 20,
                           "conf": 100, "label": "high-shelf (map)"}}
    b = match_control("high shelf", CHANNEL_EQ, control_map=cmap)
    results.append(_check("high shelf -> control-map", b, b and b["label"] == "high-shelf (map)"))

    # 6. third-party textless-ish label recovered by OCR (S3b's headline)
    b = match_control("mix", VALHALLA)
    results.append(_check("mix -> MIX", b, b and b["label"] == "MIX" and b["left"] == 177))

    # 7. non-control chrome is stoplisted
    b = match_control("default", COMPRESSOR)
    results.append(_check("default -> None (stoplist)", b, b is None))

    # --- confidence floor (S2) ------------------------------------------------
    # 7a. ambiguity gate: "gain" ties 3-way (INPUT/AUTO/OUTPUT GAIN) -> deny,
    #     never leftmost-guess INPUT GAIN.
    b = match_control("gain", COMPRESSOR)
    results.append(_check("gain -> None (3-way tie)", b, b is None))

    # 7b. clean-match gate: "mix level" matches only the 3-word run
    #     "MIX OUTPUT LEVEL" (score 2 — both tokens present, one extra), with no
    #     standalone hit -> deny rather than point at the sloppy run.
    buried = [w("MIX", 100, 100), w("OUTPUT", 160, 100), w("LEVEL", 260, 100)]
    b = match_control("mix level", buried)
    results.append(_check("score>=2 -> None (sloppy)", b, b is None))

    # 7c. legibility gate: a unique exact hit but conf below floor -> deny.
    b = match_control("attack", [w("ATTACK", 284, 475, conf=72.0)])
    results.append(_check("low-conf ATTACK -> None (conf<90)", b, b is None))

    # 7d. control: the same ATTACK at conf 100 still resolves (floor not over-tight).
    b = match_control("attack", [w("ATTACK", 284, 475, conf=100.0)])
    results.append(_check("ATTACK @100 -> hit", b, b and b["label"] == "ATTACK"))

    # 8. plugin identity from the name strip (split, joined, and single-token)
    results.append(_check("identify Compressor", None, identify_plugin(COMPRESSOR) == "Compressor"))
    results.append(_check("identify Channel EQ", None, identify_plugin(CHANNEL_EQ) == "Channel EQ"))
    results.append(_check("identify Valhalla", None,
                          identify_plugin(VALHALLA) == "Valhalla Supermassive"))

    return all(results)


def test_control_map_tier2() -> bool:
    """Verify the raw_map → _build_plugin_map → match_control tier-2 path.

    Simulates a seeded fraction entry (as returned by GET /v1/control-map) and
    confirms it routes through tier-2 instead of OCR for a textless control.
    """
    results = []

    raw_map = {
        "entries": [
            {
                "plugin": "Channel EQ",
                "control": "high shelf",
                "anchor_type": "fraction",
                "anchor": {"xfrac": 0.73, "yfrac": 0.097},
            }
        ],
        "chrome": {"top_px": 18, "total_px": 81, "scale": 2.0},
    }

    # 1. OCR alone denies — "high shelf" has no text token in the word list.
    b = match_control("high shelf", CHANNEL_EQ)
    results.append(_check("high shelf -> None (OCR alone)", b, b is None))

    # 2. _build_plugin_map resolves fraction -> pixel box.
    img_w, img_h = 2056, 1070
    built = _build_plugin_map("Channel EQ", img_w, img_h, raw_map)
    expected_cx = int(0.73 * img_w)                        # 1500
    expected_cy = int(18 + 0.097 * (img_h - 81))          # 113
    entry = built.get("high shelf")
    results.append(_check(
        "_build_plugin_map fraction -> pixel box",
        entry,
        entry is not None
        and entry["left"] + 10 == expected_cx
        and entry["top"] + 10 == expected_cy,
    ))

    # 3. Tier-2 wins — match_control with the built map returns the map entry.
    b = match_control("high shelf", CHANNEL_EQ, control_map=built)
    results.append(_check(
        "high shelf -> map hit (tier-2)",
        b,
        b is not None and b["label"] == "high shelf",
    ))

    # 4. Wrong plugin name -> empty map -> still denies (no cross-plugin leak).
    built_wrong = _build_plugin_map("Compressor", img_w, img_h, raw_map)
    b = match_control("high shelf", CHANNEL_EQ, control_map=built_wrong)
    results.append(_check(
        "wrong plugin -> empty map -> None",
        b,
        b is None and not built_wrong,
    ))

    return all(results)


if __name__ == "__main__":
    print("S2 matching layer:")
    ok1 = test_matching()
    print("\nControl-map tier-2:")
    ok2 = test_control_map_tier2()
    sys.exit(0 if (ok1 and ok2) else 1)
