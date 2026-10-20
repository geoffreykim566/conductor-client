from core.ax.controls_view import already_set, is_knob_travel, match_param, num, numeric_target
from core.ax.primitives import norm


def test_norm():
    assert norm("Channel EQ") == "channeleq"
    assert norm("Low-Cut") == "lowcut"
    assert norm(None) == ""


def test_num_reads_first_number_of_a_readout():
    assert num("-18.0 dB") == -18.0
    assert num("1,500 Hz") == 1500
    assert num("61 %") == 61
    assert num("off") is None
    assert num(None) is None


def test_match_param_exact_then_normalized_then_substring_then_fuzzy():
    rows = {"Threshold": 1, "Ratio": 2, "Low Cut Frequency": 3, "Make Up": 4}
    assert match_param(rows, "Ratio") == "Ratio"
    assert match_param(rows, "threshold") == "Threshold"
    assert match_param(rows, "Low Cut") == "Low Cut Frequency"
    assert match_param(rows, "Makeup") == "Make Up"
    assert match_param(rows, "Thresold") == "Threshold"
    assert match_param(rows, "Attack") is None


def test_already_set_compares_at_displayed_precision():
    assert already_set("-20.0 dB", -20)
    assert already_set("80 Hz", 80.4)          # Logic shows whole Hz here
    assert not already_set("-20.0 dB", -20.5)
    assert already_set("1,040 Hz", 1040)
    assert not already_set("Off", 0) and not already_set(None, 0)


def test_knob_travel_is_a_percent_matching_raw_position():
    assert is_knob_travel(40.0, 0.0, 119.0, "34 %")      # Compressor editor, live 10-19
    assert not is_knob_travel(10.0, 0.0, 200.0, "50 %")   # a real percent
    assert not is_knob_travel(0.0, 0.0, 1050.0, "20.0 Hz")
    assert is_knob_travel(61.0, None, None, "61 %")       # unverifiable % counts as travel


def test_numeric_target_applies_a_change_to_the_current_readout():
    assert numeric_target("-20.0 dB", "by:-3") == -23.0
    assert numeric_target("2.1:1", "by:1") == 3.1
    assert numeric_target("-20.0 dB", "-24") == -24.0
    assert numeric_target(None, "by:-3") is None and numeric_target("Off", "by:2") is None
