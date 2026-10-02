from core.ax.controls_view import match_param, num
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
