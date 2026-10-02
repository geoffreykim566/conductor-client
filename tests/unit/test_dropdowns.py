import pytest

from core.automation.dropdowns import _exact_option, _num_in, _option_index, _same_option, _title_for


def test_num_in():
    assert _num_in("256 Samples") == 256
    assert _num_in("1,024") == 1024
    assert _num_in("44.1 kHz") == 44.1
    assert _num_in("Mono") is None
    assert _num_in(None) is None


@pytest.mark.parametrize("want,got", [
    ("256", "256 Samples"), ("48 kHz", "48kHz"), ("Mono", "Monophonic"),
    ("Monophonic", "Flex Time - Monophonic"), ("On", "On + Align Bars"),
])
def test_same_option_loose_matches(want, got):
    assert _same_option(want, got)


@pytest.mark.parametrize("want,got", [("256", "512 Samples"), ("", "x"), ("Mono", "Stereo")])
def test_same_option_rejects(want, got):
    assert not _same_option(want, got)


def test_exact_option_has_no_loose_prefix():
    assert not _exact_option("On", "On + Align Bars")
    assert _exact_option("Slicing", "Flex Time - Slicing")
    assert _exact_option("128", "128 Samples")


def test_option_index_prefers_exact_then_loose():
    titles = ["On + Align Bars", "On", "Off"]
    assert _option_index("On", titles) == 1
    assert _option_index("Align", ["Off", "Align Bars"]) == 1   # loose prefix as a fallback
    assert _option_index("Mono", ["Stereo", "Monophonic"]) == 1
    assert _option_index("Missing", titles) is None


def test_title_for_maps_short_display_back_to_menu_title():
    shows = {"On + Align Bars": "Bars", "On": "On"}
    assert _title_for("Bars", shows) == "On + Align Bars"
    assert _title_for("Off", shows) == "Off"
    assert _title_for("Bars", None) == "Bars"
