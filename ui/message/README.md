# ui/message

A chat bubble and what attaches to it: rating buttons, the research Yes/No prompt, source
chips, and the walkthrough card that runs actions in Logic.

## Files
- `widget.py` - `MessageWidget`: the bubble, streamed text, status line; owns the card.
- `rating.py` - `RatingMixin`: Upvote/Downvote row; clicking the active button undoes the vote.
- `research_prompt.py` - `ResearchPromptMixin`: "research the web?" with Yes / No.
- `sources.py` - `SourcesMixin`: source-link chips and the (disabled) confidence badge.
- `chip.py` - `Chip`: label with its own always-on-top hover popup.
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

### Tooltips
Native tooltips render behind the frameless always-on-top window on macOS: `setToolTip()`
showed nothing (2026-09-04). `Chip` shows its own popup at the same window level; the popup
box lives on a child widget because a translucent top-level never paints its stylesheet background.

### Bubble margins
User bubbles are right-aligned, so `ChatView`'s scrollbar gutter adds to their right edge; the
user bubble's right margin subtracts `SCROLLBAR_GUTTER` to match assistant bubbles (2026-09-04).

### Confidence badges disabled
Since 2026-09-12: the server's tier is a trace rule that fired on observational answers the
KB had nothing to do with ("which tracks are muted" came back Moderate). The server sends ""
now; `set_source_tier` returns early to also cover the timeout fallback and old servers.
Styling and tooltips are kept for when the tier can tell observation from recommendation.

## Adding something under a bubble
Write a mixin (or a widget, if it has its own state machine like the card) in its own module,
add its row to `self._outer` (under the bubble) or `self._bubble_layout` (inside it), and mix it
into `MessageWidget`. Add a passthrough on `ChatView` for the current assistant bubble.
