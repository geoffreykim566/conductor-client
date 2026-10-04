# ui/onboarding

Centered, frameless dialogs: the first-run gates (Screen Recording, Input Monitoring,
Accessibility, disclaimer, optional questions) and the two periodic prompts that share their look (feedback
request, update available).

## Files
- `centered_dialog.py` - `CenteredDialog` base: window flags, translucency, fixed size, `body`, centering.
- `permissions.py` - `has_screen_recording_permission()`, `has_input_monitoring_permission()`, `has_accessibility_permission()`, plus `reset_permissions()` (called by Settings -> Uninstall).
- `screen_recording_screen.py` - `PermissionScreen` (step 1).
- `input_monitoring_screen.py` - `InputMonitoringScreen` (step 2; needed by the walkthrough interrupt tap).
- `accessibility_screen.py` - `AccessibilityScreen` (step 3; needed to post clicks and keys when a card runs).
- `disclaimer_screen.py` - beta data-collection disclaimer; marks setup complete.
- `questions_dialog.py` - experience/focus chips, sent via `put_me_async`; skippable.
- `feedback_dialog.py` - opens the feedback form; "Don't ask again" persists until the next version.
- `update_popup.py` - "Update available" with Download; reappears every launch.

## How it works
`main.py`: no Screen Recording -> `PermissionScreen`; no Input Monitoring ->
`InputMonitoringScreen`; no Accessibility -> `AccessibilityScreen`; then if setup isn't complete -> `DisclaimerScreen` -> `QuestionsDialog`
(once) -> chat. Permission screens poll every second after "Grant Access" and emit `finished`
once granted; "Skip for now" continues without it. `ChatPromptsMixin` shows the feedback dialog
when remaining messages hit `config.FEEDBACK_PROMPT_REMAINING_THRESHOLDS`, and the update popup
when `UpdateChecker` finds a newer release (checked at launch and every 6 hours).

## Quirks & why
### Two dialog aesthetics, on purpose
`CenteredDialog` (bold centered title, full-width primary button, no header) is for setup and
prompts. `ui/popup.py`'s `Popup` (header bar + close button) is for things dismissed casually
(Settings, confirms, history). Don't merge them; don't hand-roll a new frameless window either.

### Update popup has no permanent opt-out
Staying on an old version isn't a preference worth remembering; Skip only dismisses it for
this session.

### Accessibility is in setup, and still checked on Run
It was once asked only when a card's Run was first clicked (`check_event_permission`), so a
new user hit a system dialog mid-card (seen live, 2026-10-04). Setup now asks up front, using
the same `CGPreflightPostEventAccess` check. The Run-time check stays for users who skip.

## Adding a screen
Subclass `CenteredDialog(width, height)`, build `QVBoxLayout(self.body)`, use object names
`title` / `subtitle` / `primary` / `ghost` / `chip` for styling, emit a `finished` or `closed`
signal, and persist any flag through `core/state/prefs.py`. Wire it into `main.py`'s chain.
