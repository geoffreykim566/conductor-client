# core

Everything that isn't widgets: driving Logic Pro, reading its screen, talking to the server,
and local state. Nothing in core/ imports ui/.

## Files
- `events/` - tagged synthetic keyboard/mouse input and the cooperative stop signal (bottom layer).
- `ax/` - Accessibility toolkit for Logic Pro, plus the per-turn AX state dump.
- `capture/` - Logic window capture and Apple Vision OCR.
- `automation/` - the walkthrough executor: translate, run, verify, revert; its QThreads and interrupt tap.
- `net/` - server-v3 API, chat streaming, update check, and the QThread workers for them.
- `state/` - config.json (token, prefs, flags), chat history, the in-memory conversation.

## How it works
Import direction, lowest first: `events` <- `ax`, `capture` <- `automation`; `state` <- `net`.
`ui/` sits on top and imports from any of them. Keep it that way: a lower package importing a
higher one recreates the old executor/ax import cycle.

## Quirks & why
### Why events/ exists
Synthetic input used to live in the executor, which imported the AX module, which imported the
executor back (via lazy function-level imports). Moving input into its own bottom package lets
ax/ use it without depending on the executor at all.

## Adding a module
Pick the lowest package whose concern fits, import only downward, and give the module one
concern you can state in a sentence. Update that package's README `## Files`.
