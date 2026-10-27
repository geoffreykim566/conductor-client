# core/state

Local state. Persistent files live under `config.APP_SUPPORT_DIR`
(`~/Library/Application Support/Conductor`); the in-memory conversation drives the chat UI.

## Files
- `data_dir.py` - `prepare_data_dir()`: first thing in `main()`, moves `Conductor-v3` in and clears pre-v3 leftovers.
- `config_store.py` - `read_config()` / `write_config()` for the single `config.json`.
- `identity.py` - the server-minted identity token (`conductor_token`).
- `prefs.py` - auto-run, auto research, window size/position, onboarding and feedback flags.
- `song_history.py` - all chat sessions in `history.json`.
- `conversation.py` - `Conversation` / `Message`: the ordered messages of the open session.
- `run_log.py` - tees stdout/stderr into a 2000-line in-memory buffer for bug reports.
- `recent_context.py` - the last 3 turns' AX dumps and the last card's steps, in memory, for bug reports.

## How it works
`config.json` keys: `conductor_token`, `auto_run_actions`, `auto_research`, `window_width`, `window_height`,
`window_x`, `window_y`, `setup_complete`, `questions_asked`, `feedback_never_show`,
`feedback_last_version`. Every accessor does read-modify-write of the whole file through
`config_store`, so modules never clobber each other's keys. A missing or corrupt file reads as `{}`.

`history.json` is `{"sessions": [{id, messages, server_history}]}`. `server_history` is the
opaque blob the server returns; always pass the current value to `save_session` (a missing one
overwrites it with None). `Conversation` is display-only; what is sent each turn is the new
text plus that blob.

## Quirks & why
### The data dir is "Conductor", moved in from "Conductor-v3"
Until v0.4.3 the data lived in `Conductor-v3`, because pre-v3 builds (up to v0.2.6) used
`Conductor` and the two mustn't share a token or history. v0.4.3 drops the version from the name
(no names carry a version, user call 2026-10-27): at launch, `prepare_data_dir()` moves
`Conductor-v3` into `Conductor`, replacing any pre-v3 data there; with no `Conductor-v3`, pre-v3
data alone is cleared, since its token and history don't carry over. A marker file
(`config.DATA_DIR_MARKER`) records that the dir is current. "Conductor" is a common app name,
so `config` only uses it when it's empty or ours (our marker, or a `config.json` with
`conductor_token`); another app's data there is never touched, and we use
`com.conductor.logicpro` instead. Uninstall (Settings and `uninstall.sh`) removes any leftover
`Conductor-v3` too.

### One file for token and prefs
`identity.py` and the old `setup_screen.py` each had their own copy of the config.json reader;
both now go through `config_store`. Legacy `device_id` entries from pre-token builds are
ignored: unsigned, so the server would reject them anyway.

### Bug-report context lives in memory only
AX dumps aren't in `history.json`, so `recent_context` keeps the last few for a report, plus a
fresh capture at send time. `run_log` exists because the packaged app has no console
(`sys.stdout` is None), so the buffer is its only log; `main.py` installs it before the first print.

### Feedback opt-out resets per version
`reset_feedback_for_new_version()` clears "Don't ask again" whenever `config.VERSION` changes.

## Adding a preference
Add a getter/setter pair to `prefs.py` using `read_config()` / `write_config()`, list the key
above, and add a round-trip test in `tests/unit/test_state.py` (the `tmp_config` fixture
redirects `config_store.CONFIG_PATH`).
