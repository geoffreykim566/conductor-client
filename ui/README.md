# ui

The PySide6 front end: a frameless, always-on-top chat window that floats over Logic Pro,
its popups, and the first-run screens. Styling is one app-wide stylesheet (`style.py`) built
only from tokens in `theme.py`.

## Files
- `chat_window.py` - `ChatWindow`: layout, geometry persistence, chat/history paging, key routing.
- `chat_turns.py` - mixin: send a message, stream the reply, research confirm, cancel, errors.
- `chat_sessions.py` - mixin: load/switch/new/clear sessions, persist ratings.
- `chat_prompts.py` - mixin: feedback prompt and update-available popup.
- `minimized_bubble.py` - the draggable circle shown while the window is minimized.
- `chat_view.py` - `ChatView`: scrolling column of `MessageWidget`s, turn anchoring.
- `top_fade_effect.py` - graphics effect fading the chat view's top edge to transparent.
- `input_bar.py` - text field, send button, image attachments, and the controls row.
- `session_list.py` - the history page. `settings_panel.py` - Settings popup (auto-run, reset, delete, uninstall).
- `popup.py` - `Popup` base (header bar + close) for casually dismissed windows.
- `overlay_window.py` - click-through arrow overlay; only `dismiss()` is called today.
- `style.py` - `STYLESHEET`. `theme.py` - every color/size/radius token.
- `message/` - chat bubbles and the walkthrough card. `onboarding/` - centered dialogs.

## How it works
`main.py` gates on permissions and onboarding, then shows `ChatWindow`. A send goes
`InputBar.send` -> `ChatTurnsMixin._on_user_send` -> `StreamWorker` (core/net) whose signals
stream into the current assistant bubble. On `done`, the bubble gets rating buttons and, if
the server sent `walkthrough_steps`, a `WalkthroughCard`. Enter/Esc are routed in
`ChatWindow.eventFilter`: research prompt first, then cancel, then the card's Run/Revert.

## Quirks & why
### Translucent window
With an app-wide stylesheet, Qt paints an opaque default fill on any widget without a rule.
The window turns `WA_StyledBackground` off to stay see-through and draws its backdrop panel in
`paintEvent`: a toggled QSS rule on the window didn't reliably repaint (translucent frameless
top-level with zero-margin children). The backdrop is permanent because Logic showing through
the blank space behind bubbles read as chaotic (2026-09-04).

### Controls row placement
New-chat/history/minimize/close sit above the bubbles on the backdrop panel (moved there from
the input bar 2026-09-04, user preference). The main layout has zero spacing: the gap is the
controls row's own bottom margin, one lever instead of margin+spacing stacking unevenly.

### Window drag handle
The controls row is the window's drag handle. Until 6b28d41 (2026-09-12) a margin outside
the input panel did that job; that commit zeroed the margin (it was also an invisible strip
catching stray clicks) and left no way to move the window. Dragging through the row's own
background can't drift from the visible layout, since child buttons win hit testing.

### Turn anchoring
A new user message is anchored about 1/3 down the viewport once, and the view then holds
still while the reply streams. Pinning to the bottom dragged read text up past the fade on
every chunk. Fixes found live (2026-09-04): the leading spacer must be able to shrink (the
first message needs it); `processEvents()` instead of a guessed number of `singleShot(0)`
ticks (pending layout events vary); a trailing spacer reserves scroll room before
`bar.setValue()` or it clamps and snaps; that reserve is released when the turn ends or it
becomes permanent blank space. `_FADE_HEIGHT` is 24 px (40 was tuned for an old drag header),
and scrolling must call `update()` because viewport blits never re-run the fade effect.

### Geometry saved only after construction
`_geometry_ready` keeps the constructor's own resize/move from being saved, which would
otherwise shadow any later default-size change in `theme.py`.

## Adding UI
Put shared tokens in `theme.py` and rules in `style.py` (object names, not inline styles,
unless the value is one-off). A new chat-window behaviour gets its own mixin module if it
adds more than a couple of methods. Never block the UI thread on network or AX calls: use a
QThread and stop()+wait() it before teardown.
