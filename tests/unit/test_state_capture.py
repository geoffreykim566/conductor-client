from core.ax.state_capture import _help_name, _slider_value


def test_help_name_takes_the_control_name_before_its_kind():
    assert _help_name("Ratio knob and field. Set the compression ratio.") == "Ratio"
    assert _help_name("Limiter Threshold knob and field. Set the threshold.") == "Limiter Threshold"
    assert _help_name("Distortion knob. Choose whether to apply clipping.") == "Distortion"
    assert _help_name("Side Chain pop-up menu. Choose a side chain source.") == "Side Chain"
    assert _help_name("") is None
    assert _help_name(None) is None


def test_real_readouts_pass_through():
    # Channel EQ editor, live 10-19.
    assert _slider_value(0.0, 0.0, 1050.0, "20.0 Hz") == "value='20.0 Hz'"
    assert _slider_value(240.0, 0.0, 480.0, "0.0 dB") == "value='0.0 dB'"
    assert _slider_value(36.0, 0.0, 127.0, "0.71 ") == "value='0.71'"


def test_percent_equal_to_knob_travel_is_a_position():
    # Compressor editor, live 10-19: the readout is raw's place in its range.
    assert _slider_value(40.0, 0.0, 119.0, "34 %") == "position=34%"
    assert _slider_value(40.0, 0.0, 110.0, "36 %") == "position=36%"
    assert _slider_value(60.0, 0.0, 100.0, "60 %") == "position=60%"


def test_percent_that_isnt_travel_is_a_real_value():
    assert _slider_value(10.0, 0.0, 200.0, "50 %") == "value='50 %'"


def test_percent_without_a_range_counts_as_travel():
    assert _slider_value(61.0, None, None, "61 %") == "position=61%"


def test_no_readout_falls_back_to_raw():
    assert _slider_value(90.0, 0.0, 300.0, None) is None
    assert _slider_value(90.0, 0.0, 300.0, "") is None
