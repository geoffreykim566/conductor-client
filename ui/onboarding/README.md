# ui/onboarding

Centered, frameless dialogs: the first-run gates (one permission screen for Accessibility and
Screen Recording, disclaimer, optional questions) and the two periodic prompts that share their look (feedback
request, update available).

## Files
- `centered_dialog.py` - `CenteredDialog` base: window flags, translucency, fixed size, `body`, centering.
- `permissions.py` - the two permissions setup asks for (`setup_permissions()`: check, request, pane, macOS's name for each), `all_granted()`, `active_index()`, `accessibility_name()`, plus `reset_permissions()` (called by Settings -> Uninstall).
- `permissions_screen.py` - `PermissionsScreen`: a row per permission, asked one at a time.
- `disclaimer_screen.py` - beta data-collection disclaimer with the privacy policy link; accepting it marks setup complete and records `DISCLAIMER_VERSION`.
- `questions_dialog.py` - experience/focus chips, sent via `put_me_async`; skippable.
- `feedback_dialog.py` - opens the feedback form; "Don't ask again" persists until the next version.
- `update_popup.py` - "Update available" with Download; reappears every launch.

## How it works
`main.py`: either permission missing -> `PermissionsScreen`; then if setup isn't complete or the disclaimer accepted is older than `prefs.DISCLAIMER_VERSION` -> `DisclaimerScreen` -> `QuestionsDialog`
(once) -> chat. The permission screen:
- Only the first missing row has a live Grant Access. It calls that permission's request, which
  shows macOS's popup; the popup's own button opens System Settings. The screen never opens
  Settings by itself: after the click the row shows "Didn't see a popup? Open System Settings"
  as the fallback (macOS shows the popup only once).
- The click drops the window below the popup; a grant brings it back to the front.
- It re-checks every second. Accessibility ticks in place and the next row goes live. Screen
  Recording only shows as granted after macOS's own quit and reopen; the reopened app finds
  both granted and goes straight on. "Skip for now" continues; the screen returns next launch.

`ChatPromptsMixin` shows the feedback dialog when remaining messages hit `config.FEEDBACK_PROMPT_REMAINING_THRESHOLDS`, and the update popup
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

### Two permissions, not three, and in this order (2026-10-30)
Input Monitoring is no longer asked. The walkthrough interrupt tap is an active tap, and live
tests on macOS 27 showed it starts with Accessibility on and Input Monitoring off, and fails with
Accessibility off and Input Monitoring on. Accessibility is needed anyway to click and type.
Accessibility is asked first because its grant is seen live; Screen Recording's needs a quit and
reopen, so last means one reopen, at the end. `reset_permissions()` still resets ListenEvent
for older installs.

### The same requests as the old one-per-screen setup, nothing more
A first one-screen version (`v044-perms`, dropped) added a fresh-process probe, a key-tap
request for Input Monitoring, saved "already requested" flags that made a click open System
Settings on top of the popup, and its own relaunch; live it stacked popups and Settings
(2026-10-30). The old screens' requests worked once the Mac had a single registered
Conductor.app (it had 15 across the Trash, `dist/` folders and DMG volumes). This screen keeps
exactly those requests and checks. When testing setup, unregister stale copies
(`lsregister -u`) and `tccutil reset` first.

### macOS 27 renamed Accessibility
System Settings calls it "Device Control and Data Access" from macOS 27; the service and APIs
are unchanged. `accessibility_name()` picks the name by version for the screen and the card's
"Needs … permission" message.

### Accessibility is in setup, and still checked on Run
It was once asked only when a card's Run was first clicked (`check_event_permission`), so a
new user hit a system dialog mid-card (seen live, 2026-10-04). Setup now asks up front, using
the same live check (`core.events.tag.check_event_permission`, see core/events README). The
Run-time check stays for users who skip.

## Adding a screen
Subclass `CenteredDialog(width, height)`, build `QVBoxLayout(self.body)`, use object names
`title` / `subtitle` / `primary` / `ghost` / `chip` for styling, emit a `finished` or `closed`
signal, and persist any flag through `core/state/prefs.py`. Wire it into `main.py`'s chain.
