# ui

The PySide6 front end: a frameless, always-on-top chat window that floats over Logic Pro,
its popups, and the first-run screens. Styling is one app-wide stylesheet (`style.py`) built
only from tokens in `theme.py`.

## Files
- `chat_window.py` - `ChatWindow`: layout, geometry persistence, chat/history paging, key routing.
- `chat_turns.py` - mixin: send a message, stream the reply, research / plug-in read confirm (auto-approved by Auto research / auto-run), cancel, errors.
- `chat_sessions.py` - mixin: load/switch/new/clear sessions, persist ratings.
- `chat_prompts.py` - mixin: feedback prompt (opens the Report Bug form on Feedback) and update-available popup.
- `main_menu.py` - `MainMenu`: the ☰ menu's items (New Chat, History, Settings, Report Bug) on a `GlassMenu`.
- `feedback_form.py` - `FeedbackForm`: the Report Bug popup (Bug or Feedback, title, optional message).
- `minimized_bubble.py` - the draggable circle shown while the window is minimized.
- `chat_view.py` - `ChatView`: scrolling column of `MessageWidget`s, turn anchoring.
- `top_fade_effect.py` - graphics effect fading the chat view's top edge to transparent.
- `input_bar.py` - text field, send button, the Explain toggle under the text, image attachments, and the controls row.
- `session_list.py` - the history page. `settings_panel.py` - Settings popup (auto-run, auto research, reset, delete, uninstall, privacy policy link).
- `popup.py` - `Popup` base (header bar + close) for casually dismissed windows.
- `glass.py` - `GlassBackdrop`: native Liquid Glass (or blur) under a translucent window, one view cut to its shapes.
- `glass_menu.py` - `GlassMenu`: the one menu design (☰ and right-click), and `install_context_menus`, the app-wide right-click menu for chat text, the input field and line edits.
- `symbols.py` - SF Symbols rendered to Qt icons (header, send, bubble), and the drawn ☰ lines.
- `motion.py` - fade-ins for widgets and windows, fade-out on hide; off under Reduce motion.
- `style.py` - `STYLESHEET`. `theme.py` - every color/size/radius token.
- `checkbox_style.py` - `CheckboxStyle`: draws checkbox squares in `theme.CHECKBOX`.
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
- One glass view per window, cut to all its shapes by a layer mask, not a view per shape:
  Liquid Glass renders a short shape lighter than a tall one (over white, 46 px tall read 185
  grey vs 121 for 120 px and up; over grey 134 vs 116), so the input pill looked lighter than the
  chat panel above it (user report 2026-11-06). Masked from one view, both read the same over
  white, grey and black. A darker wash on the pill can't match it: the gap changes with what's behind.
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
be bundled and doesn't need to be. The card's step lines were Menlo until 2026-10-30 and are SF
now too (user call), so there's no mono font left in the app.

### Input field height
The text field grows with its wrapped text, up to 6 lines, then scrolls (`InputBar._fit_height`).
It used to be fixed at one line (`CONTROL_SIZE`) with viewport margins centring that line, so a
second line scrolled the first out and showed half-cut lines. One line is still `CONTROL_SIZE`
tall; each further line adds a line height and keeps the one-line top/bottom padding. It re-fits
on the document's size change (typing and width reflow) and on polish/style/font change, since
the stylesheet's font size and border-less frame only apply at polish. The send button is
bottom-aligned so it stays by the last line.

### Controls row placement
The ☰ menu, counter and minimize/close sit above the bubbles on the backdrop panel (moved there from
the input bar 2026-09-04, user preference). The main layout has zero spacing: the gap is the
controls row's own bottom margin, one lever instead of margin+spacing stacking unevenly.
New chat and history moved into the ☰ menu with Report Bug and Settings (user call 10-24);
Settings is also still in the macOS menu bar. The menu is our own glass dropdown, not a
`QMenu`: a native menu follows the system appearance and goes light in light mode.

### Menus
The ☰ menu and the right-click menu are one design, `GlassMenu` (`glass_menu.py`), so they
can't drift apart. It's ours, not Qt's `QMenu`: a native menu follows the system appearance
and goes light in light mode, and Qt's right-click menu kept Qt's own old look (user report
2026-11-06). Styled after macOS's menus (user calls 11-06/07, Notes as the reference): no
dividers, the hovered row filled with the accent purple. A row can carry a small SF Symbol
(`MENU_ICON_SIZE`, one fixed slot so labels line up); the ☰ menu's rows have one, the
right-click menu's don't. The panel is the
same glass as every other popup (the normal wash, no border; user call 11-07, matching the
definition popup). A darker wash read as a flat box, and a light rim as a hard edge.
Right-click: one app-wide event filter (`install_context_menus` in `main.py`) catches the
context-menu event for selectable labels, text edits (the event arrives on the viewport) and
line edits, so no widget needs its own code. The items are the ones Qt's menu had, minus Copy
Link Location: the links in replies are explain mode's terms, not web addresses. A widget with
its own `contextMenuPolicy` is left to Qt.

### Header icons
The ☰ is three drawn lines (`symbols.set_menu_lines`, `MENU_ICON_WIDTH`), not SF Symbols'
`line.3.horizontal`, which has fixed proportions and read too wide (user call 11-06). Minimize
and close are SF Symbols a step smaller than the other header glyphs (`WINDOW_ICON_SIZE`); close
is smaller again but semibold, since at that size the regular ✕ looked thin. The
controls stay grey on the right, not traffic lights: this is a floating panel whose minimize
and close don't do what a window's do, and colored dots would compete with the purple.

### Checkbox color
The native macOS style paints checkboxes in the Mac's system accent color and ignores Qt's palette
(tested 2026-11-03), so they'd change color from Mac to Mac. `CheckboxStyle`, a proxy under the
stylesheet, draws only the square in `theme.CHECKBOX` (the purple accent; user call). It's code,
not a QSS `::indicator` rule, because a QSS checkmark needs a bundled image and the build ships none.

### Report Bug form
The user picks Bug or Feedback (neither preselected); the note naming what's attached only
appears then, and switches with the pick. A bug always attaches the chat log, run log, Logic's
window state and versions; feedback sends only title and message unless "Include the chat and
logs" is ticked. Never a screenshot (user call 10-24). The form re-measures its height when the
note appears (`_fit_height`): the panel is pinned to its old size and hid the growth.
The app-wide key filter ignores keys while another of our windows is active, or Enter in the
form's title would press a waiting card's Run.

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
