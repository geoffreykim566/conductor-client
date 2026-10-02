import pytest
import Quartz

from core.events.keyboard import CHAR_KEYCODES, NAMED_KEYS, parse_shortcut


def test_plain_letter():
    assert parse_shortcut("I") == (CHAR_KEYCODES["i"], 0)


def test_named_key_is_case_insensitive():
    assert parse_shortcut("Escape") == (NAMED_KEYS["escape"], 0)
    assert parse_shortcut("RETURN") == (NAMED_KEYS["return"], 0)


def test_modifiers_combine():
    keycode, flags = parse_shortcut("Ctrl+Cmd+P")
    assert keycode == CHAR_KEYCODES["p"]
    assert flags == Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskCommand


def test_modifier_aliases():
    assert parse_shortcut("Option+K") == parse_shortcut("Alt+K") == parse_shortcut("opt+k")


def test_function_key():
    assert parse_shortcut("Ctrl+F2") == (NAMED_KEYS["f2"], Quartz.kCGEventFlagMaskControl)


def test_whitespace_around_parts_is_ignored():
    assert parse_shortcut(" Cmd + F ") == parse_shortcut("Cmd+F")


@pytest.mark.parametrize("spec", ["", "+", "Hyper+F", "Cmd+F13", "Cmd+é"])
def test_bad_specs_raise(spec):
    with pytest.raises(ValueError):
        parse_shortcut(spec)
