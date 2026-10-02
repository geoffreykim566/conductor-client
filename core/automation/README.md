# core/automation

The walkthrough executor: it takes the server's `walkthrough_steps`, translates them into
step dicts, and drives Logic Pro through them with synthetic input, verifying every step
(act -> verify, briefly retried, then a hard abort; never a blind continue). It also records
a revert ledger and can undo a run. `__init__.py` re-exports the public API ui/ uses.

## Files
- `wire.py` - server wire steps -> executor step dicts; derives `expect` / `skip_if_row` / `final` (pure).
- `runner.py` - `run_steps()`: dispatches each step to its handler, owns the key/menu/click handlers.
- `dropdowns.py` - the `choose` step: read the open dropdown via AX, pick, read back; option matching.
- `ax_steps.py` - `ax_open_plugin` / `ax_set_param` handlers; each returns a ledger entry.
- `revert.py` - undo a ledger, newest entry first (replays a dropdown route when needed).
- `menus.py` - open a menu-bar menu by OCR'ing its title; count/await Logic's popup-menu windows.
- `ocr_find.py` - capture Logic's windows, OCR them, find text; OCR box -> screen point helpers.
- `fuzzy_match.py` - fuzzy-find a phrase in an OCR word list (pure).
- `logic_focus.py` - activate Logic, confirm it is frontmost and on screen; which display it is on.
- `timing.py` - settle/verify timings. `errors.py` - `StepAbort`.
- `executor_thread.py` - `ExecutorThread` / `RevertThread` (QThreads the walkthrough card runs).
- `interrupt_tap.py` - CGEventTap that stops a run on any real key/click/scroll.

## How it works
1. `wire_to_steps()` maps wire keys to kinds and derives verification (`expect` = the next
   step's anchor text; a menu gets `skip_if_row` when its pane is already showing).
2. `ExecutorThread` activates Logic, waits for its windows, then calls `run_steps([step])`
   one step at a time so it can report progress and a resume point (`resume_at`).
3. Each handler checks Logic is frontmost, acts (keys/clicks via core/events, AX via core/ax),
   then verifies. Failure raises `StepAbort`; a stop raises `core.events.stop.Stopped`, which
   `run_steps` catches and cleans up after (Escapes any open menus).
4. Handlers that change state return a ledger entry; `revert()` undoes them.

Dependency direction: core/events <- core/ax <- core/automation. Nothing below imports this
package, and only `runner.py` wires the AX step handlers.

### Step kinds
- `key` - post a shortcut. Skipped when its `expect` is already showing (many shortcuts toggle).
- `menu` - click the menu-bar title, then per hop type-select the item NAME + Right/Return.
  Names, never positional arrow counts: names are what the KB verifies, positions shift.
- `click_text` - capture + OCR, click a matched string; `value` may be a list (state-dependent label).
- `click_value_of` - find a settings-row label, click the value blob to its right.
- `choose` - pick `value` (or "larger"/"smaller") in the dropdown the previous step opened.
- `ax_open_plugin`, `ax_set_param` - pure AX, see `ax_steps.py`.
Any step may carry `expect` (text that must appear after acting) and `final`.

## Quirks & why
### Menu bar is clicked, not focused
Ctrl+F2 menu-bar focus did nothing on at least one machine; the menu-bar title is always
clickable. Menu-bar text sits on a translucent strip, so its OCR runs at `min_conf=20`.

### Logic on another desktop
`activate_logic()` returns as soon as Logic is frontmost, but from another Space its windows
are still sliding in. A capture then sees nothing, a toggle pre-check reads "not showing" and
presses the key, closing what was open (an Inspector, live 2026-09-28). Hence
`wait_logic_on_screen()` before the first step.

### Covered panes
Window capture reads a window's pixels even when another window covers it. Project Settings
under the Settings window had its label visible to OCR but its dropdown covered
(2026-09-29). `is_front_window()` gates the "already showing" shortcuts and revert's short path.

### Leftover menus
An open menu or dropdown swallows every keystroke the next step posts (2026-09-22: a dropdown
left open by a route ate the plugin search's Ctrl+Cmd+P). `run_steps` Escapes any open menu
before each non-`choose` step.

### Synthetic events are tagged
Every event we post carries `SYNTHETIC_EVENT_TAG`; the interrupt tap passes tagged events
and swallows untagged ones. Without the tag a run would abort on its own first keystroke.
The tap replaced an older listen-only Shift+Escape monitor: it can consume the event and
reacts to any real input.

## Adding a step kind
1. Map the wire key in `wire.py` (and decide its `expect` derivation).
2. Write `_run_<kind>(step, log, stop_event)` in `runner.py` (or its own module if large),
   call `check_stop()` inside long loops, raise `StepAbort` on a failed check.
3. Register it in `runner._HANDLERS`; return a ledger dict if it changes state and teach
   `revert.py` its inverse.
4. Add the card label in `ui/message/walkthrough_card.py` and a test in `tests/unit/test_wire.py`.
