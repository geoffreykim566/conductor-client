from core.automation.fuzzy_match import _edit_distance, _tokens_match, fuzzy_match_menu_item


def word(text, left, top=10, width=None, height=12):
    return {"text": text, "left": left, "top": top, "width": width or 8 * len(text), "height": height}


def test_edit_distance():
    assert _edit_distance("kitten", "kitten") == 0
    assert _edit_distance("kitten", "sitting") == 3
    assert _edit_distance("", "abc") == 3


def test_tokens_match_tolerates_small_ocr_errors_and_ellipsis():
    assert _tokens_match(["settings"], ["setings"])
    assert _tokens_match(["manager"], ["manager…"])
    assert not _tokens_match(["mute"], ["solo"])
    assert not _tokens_match(["a", "b"], ["a"])


def test_finds_multiword_target_and_returns_union_box():
    words = [word("Sample", 0), word("Rate:", 60)]
    box = fuzzy_match_menu_item("Sample Rate", words)
    assert box["left"] == 0
    assert box["width"] == 60 + 8 * len("Rate:")
    assert box["label"] == "Sample Rate"


def test_reading_order_ignores_one_pixel_top_jitter():
    words = [word("Rate:", 60, top=10), word("Sample", 0, top=11)]
    assert fuzzy_match_menu_item("Sample Rate", words) is not None


def test_exact_row_beats_substring_of_longer_item():
    words = [word("Bypass", 0, top=10), word("All", 60, top=10), word("Control", 90, top=10),
             word("Surfaces", 150, top=10),
             word("Control", 0, top=40), word("Surfaces", 60, top=40)]
    box = fuzzy_match_menu_item("Control Surfaces", words)
    assert box["top"] == 40


def test_no_match_and_empty_target():
    assert fuzzy_match_menu_item("Metronome", [word("Tempo", 0)]) is None
    assert fuzzy_match_menu_item("...", [word("Tempo", 0)]) is None
