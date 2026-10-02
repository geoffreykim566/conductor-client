# core/state

Local state. Persistent files live under `config.APP_SUPPORT_DIR`
(`~/Library/Application Support/Conductor-v3`); the in-memory conversation drives the chat UI.

## Files
- `config_store.py` - `read_config()` / `write_config()` for the single `config.json`.
- `identity.py` - the server-minted identity token (`conductor_token`).
- `prefs.py` - auto-run, window size/position, onboarding and feedback flags.
- `song_history.py` - all chat sessions in `history.json`.
- `conversation.py` - `Conversation` / `Message`: the ordered messages of the open session.

## How it works
`config.json` keys: `conductor_token`, `auto_run_actions`, `window_width`, `window_height`,
`window_x`, `window_y`, `setup_complete`, `questions_asked`, `feedback_never_show`,
`feedback_last_version`. Every accessor does read-modify-write of the whole file through
`config_store`, so modules never clobber each other's keys. A missing or corrupt file reads as `{}`.

`history.json` is `{"sessions": [{id, messages, server_history}]}`. `server_history` is the
opaque blob the server returns; always pass the current value to `save_session` (a missing one
overwrites it with None). `Conversation` is display-only; what is sent each turn is the new
text plus that blob.

## Quirks & why
### One file for token and prefs
`identity.py` and the old `setup_screen.py` each had their own copy of the config.json reader;
both now go through `config_store`. Legacy `device_id` entries from pre-token builds are
ignored: unsigned, so the server would reject them anyway.

### Feedback opt-out resets per version
`reset_feedback_for_new_version()` clears "Don't ask again" whenever `config.VERSION` changes.

## Adding a preference
Add a getter/setter pair to `prefs.py` using `read_config()` / `write_config()`, list the key
above, and add a round-trip test in `tests/unit/test_state.py` (the `tmp_config` fixture
redirects `config_store.CONFIG_PATH`).
