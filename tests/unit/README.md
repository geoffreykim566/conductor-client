# tests/unit

Fast pytest suite for the client's pure logic. Imports pyobjc and PySide6 modules (they load
fine headless) but never needs Logic Pro, a QApplication, permissions, or the network.

## Files
- `conftest.py` - `tmp_config` / `tmp_history` fixtures that point config.json / history.json at a temp dir.
- `test_keyboard.py` - `parse_shortcut`: keys, modifiers, aliases, bad specs.
- `test_wire.py` - `wire_to_steps`: kind mapping, derived `expect` / `skip_if_row` / `final`.
- `test_fuzzy_match.py` - OCR phrase matching, reading order, exact-row preference.
- `test_dropdowns.py` - dropdown option matching (`_same_option`, `_exact_option`, `_option_index`, `_title_for`).
- `test_ocr_geometry.py` - OCR box -> screen point, value blob right of a label.
- `test_ax_pure.py` - `norm`, readout `num`, parameter-name `match_param`.
- `test_state.py` - config_store, identity, prefs, song_history, Conversation.
- `test_update_checker.py` - version parsing.

## How it works
Run `.venv/bin/python -m pip install -r requirements-dev.txt` once, then
`.venv/bin/python -m pytest` from the repo root (config in `pytest.ini`). Tests run in well under
a second.

## Quirks & why
### Private helpers are tested directly
Matching helpers such as `dropdowns._same_option` stay private to their module but carry the
logic most likely to regress, so tests import them by name. Rename them and the tests follow.

### Never write to the real app-support dir
Anything that touches `config.json` or `history.json` must use the fixtures; without them a
test would edit your real `~/Library/Application Support/Conductor-v3`.

## Adding a test
Prefer extracting a pure function over mocking AppKit/AX. One file per module area; plain
`assert`s; parametrize tables of cases.
