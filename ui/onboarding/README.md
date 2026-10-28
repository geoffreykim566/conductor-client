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
- `disclaimer_screen.py` - beta data-collection disclaimer with the privacy policy link; accepting it marks setup complete and records `DISCLAIMER_VERSION`.
- `questions_dialog.py` - experience/focus chips, sent via `put_me_async`; skippable.
- `feedback_dialog.py` - opens the feedback form; "Don't ask again" persists until the next version.
- `update_popup.py` - "Update available" with Download; reappears every launch.

## How it works
`main.py`: no Screen Recording -> `PermissionScreen`; no Input Monitoring ->
`InputMonitoringScreen`; no Accessibility -> `AccessibilityScreen`; then if setup isn't complete or the disclaimer accepted is older than `prefs.DISCLAIMER_VERSION` -> `DisclaimerScreen` -> `QuestionsDialog`
(once) -> chat. Permission screens poll every second after "Grant Access" and emit `finished`
once granted; "Skip for now" continues without it. `ChatPromptsMixin` shows the feedback dialog
when remaining messages hit `config.FEEDBACK_PROMPT_REMAINING_THRESHOLDS`, and the update popup
when `UpdateChecker` finds a newer release (checked at launch and every 6 hours).

## Quirks & why
### Two dialog aesthetics, on purpose
`CenteredDialog` (bold centered title, full-width primary button, no header) is for setup and
prompts. `ui/popup.py`'s `Popup` (header bar + close button) is for things dismissed casually
(Settings, confirms, history). Don't merge them; don't hand-roll a new frameless window either.

### The disclaimer is the consent, so it must match what's sent
It lists what goes to the server and links the website's `privacy.html` (`config.PRIVACY_URL`);
keep the two in step. When the wording changes what a user agrees to, bump
`prefs.DISCLAIMER_VERSION`: returning users see it once more before chat. The v1 text (no
version recorded) didn't mention screenshots, so v2 is shown to everyone (2026-10-27).
OpenAI and the contact email aren't here (user call): the privacy page has both.

### Update popup has no permanent opt-out
Staying on an old version isn't a preference worth remembering; Skip only dismisses it for
this session.

### Accessibility is in setup, and still checked on Run
It was once asked only when a card's Run was first clicked (`check_event_permission`), so a
new user hit a system dialog mid-card (seen live, 2026-10-04). Setup now asks up front, using
the same live check (`core.events.tag.check_event_permission`, see core/events README). The
Run-time check stays for users who skip.

## Adding a screen
Subclass `CenteredDialog(width, height)`, build `QVBoxLayout(self.body)`, use object names
`title` / `subtitle` / `primary` / `ghost` / `chip` for styling, emit a `finished` or `closed`
signal, and persist any flag through `core/state/prefs.py`. Wire it into `main.py`'s chain.
