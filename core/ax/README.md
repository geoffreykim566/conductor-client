# core/ax

Accessibility-API toolkit for driving Logic Pro directly (no OCR): find elements, press them,
open plugins, read and write plugin parameters, select tracks. Use the flat namespace
(`from core import ax`; `ax.select_track(mw, "Audio 1")`). `state_capture.py` is separate:
the passive per-turn AX text dump sent to the server as context.

## Files
- `primitives.py` - attribute get/set, press, role/title/desc/value, center, `wait_until`, `norm`, `AxError`.
- `search.py` - `find_child`, `find_anywhere`, `find_all`.
- `app.py` - Logic's pid / app element / windows / main window; raise and keep windows on screen.
- `mouse.py` - tagged synthetic clicks; `press_or_click` (AXPress, then a real click).
- `menus.py` - the open AXMenu, open a popup button's menu, drill by titles, dismiss; read a menu-bar item's checkmark.
- `channel_strip.py` - a track's strip, its FX slots, the slot holding a plugin; Stereo Out's Mastering slot.
- `plugin_windows.py` - which window shows which plugin; close one.
- `plugins.py` - add a plugin by search (Mastering Assistant: press its slot), open a loaded one, remove one.
- `controls_view.py` - parameters via the plugin window's Controls view (current view, row readouts, exact writes, display bisection).
- `editor_view.py` - parameters in the plugin's own editor (typed value, band checkboxes).
- `tracks.py` - find/select a track header.
- `state_capture.py` - read-only text dump of every open Logic window's AX tree.

## How it works
Modules import only downward (primitives -> search/app/mouse -> menus/channel_strip ->
plugins/params/tracks) plus `core.events` for synthetic keys and the event tag. Nothing here
imports `core.automation`; step handlers that use this toolkit live there.

## Quirks & why
Rules below were live-verified on Logic Pro 12.3.1 (tests/ax_mechanics/RESULTS.md).

### Return codes are never evidence
Logic gives false success (track Mute/Solo `AXPress` returns 0 and does nothing) and false
failure (`kAXErrorCannotComplete` -25204 while the menu opens anyway). Re-read state after a
settle loop; fall back to a real click at the element's AX center (`press_or_click`).

### Menu drills end in a sub-choice
A terminal item can still open Mono / Stereo or Stereo / 5.1; `drill()` checks after the last hop.

### Plugin identity
Never match the channel-strip slot label: it is truncated and width-dependent ("Cnsl EQ").
Use the plugin window's own name (`window_plugin_name`). Plugin windows are titled after the
TRACK, so two plugins on one track give two windows with the same title (2026-09-19); compare
(title, plugin) pairs, which also covers Logic swapping the plugin inside one window.

### Controls view is the universal parameter path
Every parameter there is an `AXCell` row, and an `AXValue` write on its slider lands exactly on
every plugin tested, third-party included. Its readouts aren't writable, so a display value is
reached by bisecting raw (log-scaled for frequencies): slower and a visible sweep, hence the
editor is tried first where it labels sliders (Channel EQ does, Compressor mostly doesn't).
Plugin windows can open with the View menu off-screen; `ensure_on_screen` first.
A third-party plug-in's View menu names its editor after the plug-in ("Controls",
"ValhallaSupermassive"), not "Editor", so `set_view(..., "Editor")` picks the first item that
isn't Controls; before 10-20 every read or edit left such plug-ins in Controls view.

### Slot index is only a hint
Search-and-Add inserts at the top of the strip, so slot indexes shift as plugins come and go.
`loaded_slot` uses the add-time index only if that slot still holds the named plugin.

### Mastering Assistant is a plug-in in its own slot
It sits in a dedicated slot on the Stereo Out strip, not in a track's Audio FX slots (v043).
Empty, the slot is an `AXButton` whose help says "Click to insert Mastering Assistant"; pressing
it loads the plug-in and opens its window, the same as Mix > Mastering Assistant without the
menu. Loaded, it's a slot group (`bypass`/`open`/`list`) like any plug-in's, so open, bypass,
Controls-view reads and writes, and "No Plug-in" removal all reuse the plug-in code through
`plugin_slot` (live 10-22). Its window is titled "Stereo Out" whichever track is selected, so
callers drop `track` for it. In an empty project its window opens with an intro sheet (OK);
that's left for the user, and the window counts as open.

### Plugin load mismatch
If a search loads something whose window doesn't come up as the requested plugin, report it and
leave the slot alone. An auto-removal used to run here; on the 09-19 false mismatch it silently
failed (return value ignored), and on a real mismatch it would delete a plugin nobody asked to touch.

### No windows exposed
Logic running but exposing no AX windows means it is on another Space, minimized, or the
project is closed (2026-09-18); the step aborts with a "bring Logic to this desktop" message.

### AX state capture depth
The previous depth cap of 6 sliced off the Tracks header (Mute/Solo sit at depth 8), so
per-track mute state never reached the model (2026-09-12). Depth is now a sanity ceiling
(20); the node budget bounds capture time (~0.5 ms per node) and the char cap bounds payload.
The Tracks group is walked first so a big Inspector can't eat the budget.

### Plug-in knob values in the dump
The model gets each slider's `AXValueDescription`, not raw `AXValue`: raw numbers made it guess
conversions ("Threshold 61 on the slider (~-20 dB)", 10-12). Channel EQ's editor gives real units.
The Compressor editor gives only knob travel: every readout is a % equal to raw's place in its
range ("34 %" for raw 40 of 0–119), so a % that matches that is sent as `position=34%` and any
other % as a real value (live 10-19). The server prompt says `position=` isn't a setting; Sol
calls `read_plugin_values` for the real one. The Compressor editor names only Threshold in
`AXDescription`; the rest are named from `AXHelp` ("Ratio knob and field. ..."). No per-knob
note on `position=`: with two plug-in windows open the dump is already near its 12k cap.

### Wedged AX server
With the Mac's screen locked, Logic's AX server returned the AXApplication element for every
window attribute and as its own child (2026-09-12), so the walk produced a self-referential
chain until the depth cap. The capture stops at AXApplication and AXMenuBar nodes.

## Adding an AX operation
Put it in the lowest module whose concern it matches, import only from modules below it,
verify by re-reading state (never by return code), raise `AxError` on a failed contract, and
add it to `__init__.py`'s imports and `__all__`. Exercise it live with a script in
tests/ax_mechanics; unit-test any pure part in tests/unit.
