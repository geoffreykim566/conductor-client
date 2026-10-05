# AX execution-mechanics suite — results

**Run:** 2026-09-18, Logic Pro **12.3.1**, macOS Darwin 25.5, scratch project "Untitled"
(Audio 1, Audio 2, one software-instrument track), client venv Python with Accessibility +
Input Monitoring + Screen Recording granted. Scripts: `tests/ax_mechanics/t*.py`, toolkit
`_ax_common.py`, screenshots in `evidence/`. Run with
`PYTHONUNBUFFERED=1 .venv/bin/python -m tests.ax_mechanics.<test>` from `client/`.

Rule applied throughout: an AX action's return code is never evidence. Every PASS re-reads the
resulting AX state (fresh element lookup, settle loop) and, where noted, a screenshot.

| # | Test | Result | Evidence / numbers |
|---|---|---|---|
| T1 | Menu chains via `AXPress` (`Logic Pro > Settings > Audio…`, `File > Project Settings > Smart Tempo…`) | **PASS** | pre-resolve + back-to-back presses; new `AXWindow` in 0.47–0.57 s; closed via `AXCloseButton` in 0.5 s |
| T2 | Toggles | **PASS with caveat** | Control Bar `Inspector` checkbox: `AXPress` works. **Track-header Mute/Solo: `AXPress` and `AXValue` set both return 0 and do nothing (false success, screenshot-confirmed); a real click at the element's AX center flips it in 0.03 s** (`evidence/t2b_mute_click.png` shows M lit). |
| T3 | `AXPopUpButton` Flex Mode | **PASS** | real click → `AXUIElementCopyElementAtPosition` + `AXParent` → `AXPress` item; read-back 0.40 s; idempotent skip works; item titles are full strings ("Flex Time - Monophonic") |
| T4 | Exact slider values (track header Volume, Pan) | **PASS** | double-click → focused `AXTextField` → set → Return; read-back immediate. Volume: 10 raw/dB, 173 = 0.0 dB. Pan: raw = 64 + displayed (text "20" → raw 84). |
| T5 | Track rename | **PASS** | same text-field path; header updates in 0.03 s; reverted |
| T6a | Open **any** audio-FX plugin by name via `Ctrl+Cmd+P` | **PASS** | Phat FX, Step FX, Vintage Console EQ, ValhallaSupermassive (none in the KB) — set the search field's `AXValue` (no per-letter keystrokes), Return; loaded in 0.07–0.31 s. Verify via the plugin window's titled editor `AXGroup` — the **slot label is truncated and width-dependent** ("Cnsl EQ", "ValhallaSup"/"ValhallaSu"), never match on it. |
| T6b | Open plugin via insert-slot menu (pure AX drill) | **PASS** | empty slot `AXButton desc='audio plug-in'`: `AXPress` is inconsistent (0 with no menu, or -25204 with menu) → fall back to click; drill by title; **terminal items carry a Mono / Mono→Stereo sub-choice on a mono strip** (July's Drum Kit Designer "Stereo" hop, generalized) |
| T6c | Instrument slot → `Synthesizer > ES2 (Synthesizer 2)` | **PASS** | slot = `AXGroup` named after the patch with bypass/open/list; `AXPress` -25204 but opens; `Stereo / 5.1` terminal sub-choice; loaded in 0.15 s |
| T7 | Set a plugin parameter to an exact value | **PASS — universal mechanism found** | see below |
| T8 | Read-back settle | **measured** | 0.01–0.12 s for sliders/params (immediate); 0.40 s for the flex popup; window open ~0.5 s |
| T9 | Addressability (Tracks window) | **PASS by index** | 124 addressable nodes; role+name resolves 72/124 uniquely, **role+name+sibling-index 124/124**, stable across 3 re-resolves |
| T10 | Shortcut sweep via `executor.press()` | 8/10 | Cmd+, Option+P Cmd+K Cmd+B open windows in <0.1 s; X/Y toggle panes; Ctrl+Cmd+P focuses the search field; Cmd+F fires. **Option+T and Option+Cmd+N** fired; their panels aren't in `AXWindows` — resolved below (sheet / popover), so effectively 10/10. |
| T12 | Reversibility via Logic Undo | **PASS except param writes** | see T12 section |
| T11 | Transport / meters readable? | **PASS (transport)** | `Play`/`Record`/`Cycle`/`Metronome Click` are `AXCheckBox` with values, `Tempo` an `AXSlider` (120.0), `Record Enable` per track. **A "don't act while recording" gate is buildable.** CPU meter: not found by name. |

## T7 detail — the primitive

Editor view labelling varies wildly across Apple's own plugins: Channel EQ 26/26 sliders
labelled, Compressor 1/22, Tape Delay 0/14, ValhallaSupermassive 0/10. So name-based targeting
via the editor view does not generalize.

**Controls view is universal.** The plugin window's `AXMenuButton desc='view'` (title shows the
current view: "Editor", "Controls", or a zoom % for Apple plugins) → `AXPress` → its child
`AXMenu` → item "Controls". Every parameter then becomes an `AXCell` containing
`AXStaticText 'Label:'` + `AXGroup readout` + `AXSlider`. A **direct `AXValue` write on that
slider lands exactly** and the readout confirms it (this reverses the July "direct writes clamp"
finding, which was specific to the track fader):

| Plugin | rows | write | raw → readout |
|---|---|---|---|
| Channel EQ | 26 | Peak 1 Gain +60 raw | 299→359, "+5.9 dB"→"+11.9 dB" (10 raw/dB) |
| Compressor | 12 | Threshold +4 raw | 60→64, "-20.0 dB"→"-18.0 dB" (2 raw/dB) |
| Tape Delay | 13 | Feedback +10 raw | 61→71, "61 %"→"71 %" |
| ValhallaSupermassive (3rd-party AU) | 18 | Mix +1000 raw | 5000→6000, "0.5"→"0.6" |

Raw scale is per-parameter; the readout text gives the display scale, so a calibrated write is
"set raw, read readout, adjust" (or map once per parameter and cache). `AXIncrement` also works
(steps: 10 on Tape Delay Feedback, 500 on Valhalla Mix) but the step is unqueryable. The editor
view's double-click → text-field route still works where a slider is labelled (Channel EQ,
Compressor Threshold), but the readout `AXTextField` can lag; verify on the raw value.

## Sheets and popovers (closed 2026-09-18, after user screenshots)

- **Option+Cmd+N (Create New Track)** is an `AXSheet` (desc 'New Track') child of the main
  window, found in 0.32 s; every option (`Software Instrument`, `Mic or Line`, `Create`, `Cancel`…)
  is an addressable button by title. Escape dismisses it.
- **Option+T (Configure Track Header)** is an untitled layer-0 window that appears in
  `CGWindowListCopyWindowInfo` but NOT in `AXWindows` or the app's AX children. Locate it via
  `AXUIElementCopyElementAtPosition` inside its raw bounds → walk `AXParent` up to the `AXPopover`;
  all its checkboxes (`Mute`, `Solo`, `Input Monitoring`, `Volume`, `Track Numbers`…) are then
  addressable with values. Escape dismisses it. Rule: after any action, diff the raw window list
  as well as `AXWindows`; an untitled new window means "popover — go in by position".

## T12 — reversibility via Logic's own Undo (2026-09-18, `t12_reversibility.py`, log in `evidence/t12.log`)

Each action done via AX, then Cmd+Z, state re-read via AX:

| action | Cmd+Z reverts? |
|---|---|
| mute (real click) | yes |
| volume via text field | yes |
| rename | yes |
| insert plugin (Search-and-Add) | yes |
| remove plugin (slot menu → No Plug-in) | yes |
| delete empty track (Delete key, no confirm sheet appeared) | yes ("Undo Delete Tracks") |
| **plugin parameter via Controls-view `AXValue` write** | **no** — not in the undo history; Cmd+Z undid the plugin insert instead |

Consequences: structural actions can rely on Logic's Undo (a "revert" offer can literally press
Cmd+Z, or better, the Edit menu's Undo item via `AXPress`); parameter writes need our own
snapshot-before-write + write-back (already how every T7 test restored values). App-level
settings (buffer size etc.) were not tested here; per the July notes they are outside Undo.
Caveat: the Edit menu's "Undo …" item title lagged behind the real stack (showed a stale title
after mute), so it is not a reliable pre-check of what Cmd+Z will do.

## Cross-cutting findings

- **`AXPress` is unreliable in both directions**: false success (track Mute/Solo, T6b slot
  sometimes) and false failure (-25204 on slot/list buttons that open anyway). Always verify by
  re-reading state; fall back to a real click at the AX center when nothing changed.
- **Menu drills must handle an extra terminal hop** (Mono/Stereo, Stereo/5.1). Prefer "Stereo"
  else first.
- **Plugin window title = track name** ("Audio 1"); plugin identity = the titled editor
  `AXGroup` (or last `AXStaticText`). Slot labels are truncated.
- **Read-back is effectively immediate on 12.3.1** (≤0.12 s) except popups (0.4 s).
- Removing a plugin: slot group's `list` button → "No Plug-in" — works via AX.
- Nothing in these tests needed OCR or screen coordinates except (a) real clicks at AX-derived
  centers and (b) the double-click-to-edit gesture.

## Open

- CPU meter readability.
- Region resize (T-July category 6) not retested.
- Plugin parameter raw↔display scale map per plugin (needed for "set to 80 Hz"-style writes).
- Third-party coverage is one plugin (Valhalla); Controls view should make this moot, but confirm
  on a VST3/AU with a custom UI that hides the View menu (none installed here).
