from core.automation.editor_ocr import is_label, is_value, pick_label, pick_value
from core.ax.controls_view import all_unitless, is_unitless


def line(text, cx, cy, w=40, h=14):
    """An OCR line as (text, frame) in screen points, given its centre."""
    return (text, (cx - w / 2, cy - h / 2, w, h))


# ValhallaSupermassive editor, live 10-20: knob frames from AX, label 40 pt above, value 40 pt below.
MIX = (232, 343, 60, 60)
DELAY = (352, 346, 130, 130)
VALHALLA = [line("MIX", 262, 333), line("50.0 %", 262, 413), line("DELAY", 417, 332),
            line("300.0 ms", 417, 493), line("WIDTH", 262, 450), line("100.0 %", 262, 529)]


def test_label_and_value_words():
    assert is_label("Low Cut") and is_label("MIX") and is_label("Flutter Intensity")
    assert not is_label("Hz") and not is_label("50.0 %") and not is_label("-20") and not is_label(": 2")
    assert is_value("300.0 ms") and is_value("-5.4 dB") and is_value("20000 Hz") and is_value("0.38 Hz")
    assert is_value("1500") and not is_value("MODE: Gemini") and not is_value("Version 5.0.0 ARM AU")


def test_valhalla_knobs_take_the_label_above_and_the_value_below():
    assert pick_label(MIX, VALHALLA) == "MIX"
    assert pick_value(MIX, VALHALLA)[0] == "50.0 %"
    assert pick_label(DELAY, VALHALLA) == "DELAY"          # big knob: label 14 pt above its frame
    assert pick_value(DELAY, VALHALLA)[0] == "300.0 ms"


def test_value_point_is_where_the_value_is_drawn():
    assert pick_value(MIX, VALHALLA)[1] == (262, 413)


def test_next_rows_label_isnt_taken_for_a_value_or_name():
    width = (232, 459, 60, 60)
    assert pick_label(width, VALHALLA) == "WIDTH"
    assert pick_value(width, VALHALLA)[0] == "100.0 %"


def test_label_left_on_the_row_when_none_above():
    # Tape Delay's Smoothing: a horizontal slider, its label to the left; ": 2" above isn't a label.
    smoothing = (606.5, 544, 83, 24)
    lines = [line(": 2", 585, 507), line("Smoothing", 563, 557), line("40 ms", 672, 556)]
    assert pick_label(smoothing, lines) == "Smoothing"
    assert pick_value(smoothing, lines)[0] == "40 ms"


def test_nothing_near_gives_none():
    assert pick_label(MIX, [line("FEEDBACK", 712, 333)]) is None
    assert pick_value(MIX, [line("50.0 %", 712, 413)]) is None


def test_controls_positions_only():
    assert is_unitless("0.5") and is_unitless("1") and is_unitless("0")
    assert not is_unitless("50.0 %") and not is_unitless("2") and not is_unitless("-0.5")
    assert all_unitless(["0.5", "1", "0.2857", "Off"])                       # Valhalla's Controls rows
    assert not all_unitless(["-20.0 dB", "2.1:1", "0.7", "Platinum Digital"])  # Compressor (Knee 0.7)
    assert not all_unitless(["on", "Band Stop"])                              # nothing numeric
