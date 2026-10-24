# ui

The PySide6 front end: a frameless, always-on-top chat window that floats over Logic Pro,
its popups, and the first-run screens. Styling is one app-wide stylesheet (`style.py`) built
only from tokens in `theme.py`.

## Files
- `chat_window.py` - `ChatWindow`: layout, geometry persistence, chat/history paging, key routing.
- `chat_turns.py` - mixin: send a message, stream the reply, research / plug-in read confirm (auto-approved by Auto research / auto-run), cancel, errors.
- `chat_sessions.py` - mixin: load/switch/new/clear sessions, persist ratings.
- `chat_prompts.py` - mixin: feedback prompt and update-available popup.
- `minimized_bubble.py` - the draggable circle shown while the window is minimized.
- `chat_view.py` - `ChatView`: scrolling column of `MessageWidget`s, turn anchoring.
- `top_fade_effect.py` - graphics effect fading the chat view's top edge to transparent.
- `input_bar.py` - text field, send button, image attachments, and the controls row.
- `session_list.py` - the history page. `settings_panel.py` - Settings popup (auto-run, auto research, reset, delete, uninstall).
- `popup.py` - `Popup` base (header bar + close) for casually dismissed windows.
- `glass.py` - `GlassBackdrop`: native Liquid Glass (or blur) shapes under a translucent window.
- `symbols.py` - SF Symbols rendered to Qt icons (header, send, bubble).
- `motion.py` - fade-ins for widgets and windows, fade-out on hide; off under Reduce motion.
- `style.py` - `STYLESHEET`. `theme.py` - every color/size/radius token.
- `message/` - chat bubbles and the walkthrough card. `onboarding/` - centered dialogs.

## How it works
`main.py` gates on permissions and onboarding, then shows `ChatWindow`. A send goes
`InputBar.send` -> `ChatTurnsMixin._on_user_send` -> `StreamWorker` (core/net) whose signals
stream into the current assistant bubble. On `done`, the bubble gets rating buttons and, if
the server sent `walkthrough_steps`, a `WalkthroughCard`. Enter/Esc are routed in
`ChatWindow.eventFilter`: research or plug-in read prompt first, then cancel, then the card's Run/Revert.

## Quirks & why
### Translucent window
With an app-wide stylesheet, Qt paints an opaque default fill on any widget without a rule.
The window turns `WA_StyledBackground` off to stay see-through and draws its backdrop panel in
`paintEvent`: a toggled QSS rule on the window didn't reliably repaint (translucent frameless
top-level with zero-margin children). The backdrop is permanent because Logic showing through
the blank space behind bubbles read as chaotic (2026-09-04).

### Glass backdrop
Every window gets native glass behind Qt's drawing (`glass.py`): Liquid Glass
(`NSGlassEffectView`) on macOS 26+, the HUD blur (`NSVisualEffectView`) on 12–25, and the old
painted panel when neither works (`CONDUCTOR_GLASS=off|blur` forces a tier). Found in a live
spike (2026-10-23):
- The glass views go in the window's frame view, *under* Qt's view, so Qt's view stays the
  `contentView` (Qt's Cocoa backend moves/resizes the NSWindow itself only while it is; Qt
  moves and resizes stayed correct this way). Putting Qt's view inside the glass view's
  `contentView` made Qt draw nothing.
- No glass `tintColor`: macOS applies it only while the window is key, and this window rarely
  is (Logic is), so it went flat grey. Qt paints a dark wash (`GLASS_WASH`) over each shape instead.
- No window shadow: it traced the shapes with a heavy dark outline and greyed the glass.
- Shape frames come from Qt's size, not the native views': on a Qt resize the NSWindow can
  still have the old size, which put Settings' glass short. Setting frames on the glass
  container itself blanked whole windows.
- While the window is key, glass casts a shadow past its shapes, and the window edge cut it
  into a faint dark rectangle past the rounded corners that also sliced the pill's ends (user
  report 2026-10-23). It took both fixes, checked by pixel reads with the window key: no
  `NSGlassEffectContainerView` (it shaded the whole window rect), and each glass view's layer
  clipped to its rounded shape (`masksToBounds` + `cornerRadius`).
- Surfaces on the glass are translucent white (`theme.SURFACE*`), and the dim text greys are a
  step lighter than Apple's, since Qt text gets no vibrancy.

### Motion
New bubbles and cards fade in, windows fade in from their `showEvent`, and minimize/close fade
out first (`motion.py`). Nothing animates when macOS Reduce motion is on. QSS can't animate,
so button hovers stay instant. A reply is revealed a few characters per frame (~0.5 s for any
length, `MessageWidget`), because the server sends it as one chunk and it used to land all at
once. Sources, rating and the card wait for the reveal (`after_reveal`), and so does the
release of the turn's scroll reserve, which also animates: released while the reply was still
revealing, the view clamped down and the reply grew out of sight (2026-10-23). Sending the next
message finishes a reveal still running.

### Fonts
UI text is the app font (SF Pro, the system font; QSS rules leave `font-family` out). It can't
be bundled and doesn't need to be. Menlo (`MONO`) is kept only for the card's step lines (user
call 2026-10-23; the counter moved to SF the same day).

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
becomes permanent blank space. The scroll target uses the message's position re-measured
after the last `processEvents()`, not one derived from the first measurement: rows above
were still settling then, which put the message ~150 px low, and after a long reply ~420 px
low, just off screen (the "new message no longer snaps down" bug, 2026-10-23). `_FADE_HEIGHT` is 24 px (40 was tuned for an old drag header),
and scrolling must call `update()` because viewport blits never re-run the fade effect.

### Window equals the painted panel
No inset, no `setMask`, min size < max size. A 70 px left inset once left an invisible strip
that caught clicks and the resize cursor; with the window matching the panel, macOS's native
borderless edge resize lands on the visible edge.

### Geometry saved only after construction
`_geometry_ready` keeps the constructor's own resize/move from being saved, which would
otherwise shadow any later default-size change in `theme.py`.

## Adding UI
Put shared tokens in `theme.py` and rules in `style.py` (object names, not inline styles,
unless the value is one-off). A new chat-window behaviour gets its own mixin module if it
adds more than a couple of methods. Never block the UI thread on network or AX calls: use a
QThread and stop()+wait() it before teardown.
