# tests/ax_mechanics

Live experiments that drive Logic Pro through the Accessibility API and synthetic input to
prove (or disprove) a mechanism before core/ax relies on it. Results and numbers are in
`RESULTS.md`; screenshots in `evidence/`.

## Files
- `_ax_common.py` - shared toolkit: frontmost hard gate, AX helpers, settle loops, result/screenshot logging.
- `t1_menu_chain.py` - menu-bar chains via back-to-back AXPress.
- `t2_toggles.py` - track Mute/Solo (AXPress no-op; real click works).
- `t3_flex_popup.py` - AXPopUpButton (Flex Mode) via click + element-at-position.
- `t4_slider_exact.py` - exact track Volume/Pan via the double-click text field.
- `t5_rename.py` - track rename via the same text-field path.
- `t6_open_plugin.py` - open any plugin by name (search field, slot menu, instrument slot).
- `t7_set_param.py` - set a plugin parameter exactly (Controls view; imports from t6).
- `t9_addressability.py` - read-only: how uniquely AX paths resolve.
- `t10_shortcuts.py` - shortcut sweep via `core.events.keyboard.press` with the frontmost gate.
- `t11_transport.py` - read-only: transport, tempo, meters.
- `t12_reversibility.py` - which actions Logic's own Undo reverts (imports from t6 and t7).

## How it works
Open a scratch project (Audio 1, Audio 2, one software-instrument track), grant Accessibility,
Input Monitoring and Screen Recording to `.venv/bin/python`, then from the repo root:
`PYTHONUNBUFFERED=1 .venv/bin/python -m tests.ax_mechanics.t6_open_plugin`. Every script
activates Logic, HARD-GATES on `frontmost_owner()`, captures a baseline, re-checks frontmost
after every action, and verifies by re-reading AX state after a settle loop.

## Quirks & why
### These change your project
They add plugins, rename tracks and toggle state (most revert themselves, not all). Never run
them against a real session. They are not collected by pytest.

### Own toolkit on purpose
`_ax_common.py` predates core/ax and keeps its own primitives so an experiment can try a
mechanism the production toolkit doesn't have. It imports only `activate_logic` /
`frontmost_owner` (core.automation.logic_focus) and `press` (core.events.keyboard) from the app,
and adds the repo root to `sys.path` itself.

## Adding an experiment
Copy the shape of an existing `t<N>_*.py`: `from tests.ax_mechanics._ax_common import *`,
`bring_logic_front()`, act, `wait_until(...)` on re-read state, `result(name, ok, detail)`.
Record the outcome in `RESULTS.md`; promote a proven mechanism into core/ax.
