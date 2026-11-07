# ui/message

A chat bubble and what attaches to it: rating buttons, the research Yes/No prompt, source
chips, and the walkthrough card that runs actions in Logic.

## Files
- `widget.py` - `MessageWidget`: the bubble, streamed text (revealed gradually, `after_reveal`), status line; owns the card.
- `rating.py` - `RatingMixin`: Upvote/Downvote row; clicking the active button undoes the vote.
- `research_prompt.py` - `ResearchPromptMixin`: "research the web?" with Yes / No.
- `sources.py` - `SourcesMixin`: source-link chips (research turns).
- `terms.py` - `TermsMixin`: underlines the reply's glossary terms (the server's `terms`); `TermPopup` shows a definition on click.
- `walkthrough_card.py` - `WalkthroughCard`: step list, buttons, hint/status lines, view states.
- `walkthrough_run.py` - `WalkthroughRunMixin`: start/stop the executor and revert threads, outcomes.
- `styles.py` - shared label styles and `system_font()`.

## How it works
`ChatView.setup_walkthrough_card()` -> `MessageWidget.setup_walkthrough()` creates a
`WalkthroughCard`. Card states: `ready` -> `running` -> `done` (Revert offered when the ledger is
non-empty) or `retry` after a failure/stop (Try again resumes at `ExecutorThread.resume_at`;
Revert offered if something changed) -> `reverting` -> `reverted` / `revert_failed`. Enter calls
`wt_enter()` which maps to Run / Revert / Try again for the current state. `auto` runs it
straight away unless any step is `destructive`.

A run arms `WalkthroughInterruptTap` first: any real key/click/scroll sets the stop event
(instant) and queues `_on_stopped` (the teardown waits up to 2 s, too long for a tap callback).

## Quirks & why
### QThread teardown
Qt6 aborts the process (`qFatal`) when a QThread is destroyed while running; this showed up as
recurring "Python crashed" reports. Anything that can delete a card (new chat, app quit) calls
`force_end_walkthrough()`, which stops and waits for every worker.

### Try again and the shared ledger
Try again makes no server call: the card's goal hasn't changed and every step re-reads live
state. It resumes just past the last step that changed something, so "one step larger" or a
second-copy add isn't repeated. All attempts share one ledger and Revert runs newest first, so
a value changed twice ends at its original. A failed Revert keeps only its failed entries.

### No typed revert
User call: "undo that" in chat is declined (server-side) and points at the card. Revert stays
live on older cards after later turns, which is the only undo path for now.

### Tooltips
Native tooltips render behind the frameless always-on-top window on macOS: `setToolTip()`
showed nothing (2026-09-04). The confidence badge's `Chip` (removed 2026-10-21, in git history)
showed its own popup at the same window level instead; the popup box lived on a child widget
because a translucent top-level never paints its stylesheet background.

### Glossary popup
`TermPopup` is just the definition and a Read more link (no title or close button, user call 2026-11-06). It closes on a click anywhere else in the app (an app-wide event filter), not on focus loss:
the chat window takes focus straight back when the popup opens, so it closed the moment it appeared
(2026-11-06). Terms render once the reveal finishes (`after_reveal`); the label switches to rich text
with `term:<i>` links, and a saved message keeps its `terms` so a reloaded chat underlines them too.

### Plug-in step text
A plug-in step shows what the client actually does, one numbered line per keypress ("Press ⌃⌘P",
"Type Compressor", "Press Return"; `core/ax/plugins.py`), so a beginner can repeat it: "Open
Compressor" taught nothing (user call 2026-11-06). One wire step can show as several lines, so
`_step_labels[i]` is wire step i's list and they highlight together. Mastering Assistant keeps
"Open": it has its own slot on Stereo Out.

### Bubble margins
User bubbles are right-aligned, so `ChatView`'s scrollbar gutter adds to their right edge; the
user bubble's right margin subtracts `SCROLLBAR_GUTTER` to match assistant bubbles (2026-09-04).

## Adding something under a bubble
Write a mixin (or a widget, if it has its own state machine like the card) in its own module,
add its row to `self._outer` (under the bubble) or `self._bubble_layout` (inside it), and mix it
into `MessageWidget`. Add a passthrough on `ChatView` for the current assistant bubble.
