# core/events

The bottom layer: synthetic CGEvent input that every other module posts through. Each event
is tagged as Conductor's own, and posting loops check a cooperative stop flag between events so
a run can be interrupted mid-step.

## Files
- `tag.py` - `SYNTHETIC_EVENT_TAG`, `tag_synthetic()`, `check_event_permission()` (live Accessibility check).
- `stop.py` - `Stopped` and `check_stop(stop_event)`.
- `keyboard.py` - US-ANSI keycode tables, `parse_shortcut`, `post_key`, `press`, `type_select`.
- `mouse.py` - `click_at(x, y)` in global screen points (top-left origin, same as kCGWindowBounds).

## How it works
`press("Ctrl+Cmd+P")` -> `parse_shortcut` -> `post_key` posts key down/up, tagging each event and
calling `check_stop()` first. `type_select` types item names into a focused menu (trailing
ellipsis stripped; spaces are typed because NSMenu's incremental search uses them).

## Quirks & why
### Why tag every event
`core.automation.interrupt_tap` swallows any untagged key/click/scroll during a run. An
untagged synthetic event would abort the run on its own first keystroke.

### Accessibility is checked with AXIsProcessTrusted
`CGPreflightPostEventAccess` stayed False in the running app after the user switched
Accessibility on (macOS had written the grant; seen live 2026-10-04), so setup sat on "Waiting
for approval". `AXIsProcessTrusted` reads the live state and needs no relaunch. The prompt is
`AXIsProcessTrustedWithOptions`; `CGRequestPostEventAccess` showed none.

### Stop is cooperative
`Stopped` is raised from inside posting loops (per character, per menu hop), not between
steps, so a real keypress stops a run within about one keystroke. `run_steps` catches it and
closes any menus left open; it is never reported as a failure.

## Adding input
Keep this package free of imports from core/ax or core/automation. New keys go in the tables
in `keyboard.py`; anything that posts must call `tag_synthetic()` and `check_stop()`. Add a
case to `tests/unit/test_keyboard.py`.
