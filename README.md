# Conductor client (v3)

The macOS desktop app for Conductor (https://askconductor.ai): a floating chat window over Logic
Pro that answers questions using screenshots and Accessibility state of your session, and can run
the steps it suggests (menus, shortcuts, dropdowns, plugins, parameters) with verify and revert.
Python 3, PySide6 for UI, pyobjc for Quartz / Accessibility / Vision, packaged with PyInstaller.

## Layout
- `main.py` - entry point: permission + onboarding chain, then the chat window.
- `config.py` - version, data dir, server URL, capture limits.
- `core/events/` - tagged synthetic keyboard/mouse input; cooperative stop.
- `core/ax/` - Accessibility toolkit for Logic Pro; per-turn AX state dump.
- `core/capture/` - window capture and Vision OCR.
- `core/automation/` - walkthrough executor: wire translation, step runner, revert, interrupt tap.
- `core/net/` - server-v3 API, chat streaming, update check, worker threads.
- `core/state/` - config.json, chat history, conversation model.
- `ui/` - chat window and its parts; `ui/message/` bubbles + walkthrough card; `ui/onboarding/` dialogs.
- `tests/unit/` - pytest; `tests/ax_mechanics/` - live Logic Pro experiments.
- `build.sh`, `conductor.spec`, `entitlements.plist` - packaging. `uninstall.sh` - user uninstaller.

Each folder has a README with its files, flow, quirks, and how to extend it.

## Run in dev
```
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python main.py                                          # against https://api.askconductor.ai
CONDUCTOR_SERVER_URL=http://127.0.0.1:8000 .venv/bin/python main.py   # against a local server-v3
```
For a local server run `docker compose up -d --build` inside `server-v3/`. On first launch macOS
asks for Screen Recording, Input Monitoring and Accessibility (the last is needed to run actions).
In dev these are granted to the terminal / Python binary, not to Conductor.app.

## Tests
- Unit: `.venv/bin/python -m pytest` (scoped to `tests/unit` by `pytest.ini`; no Logic needed).
- Live: `PYTHONUNBUFFERED=1 .venv/bin/python -m tests.ax_mechanics.<t_name>` with a scratch Logic
  project open. These change the project; see `tests/ax_mechanics/README.md`.
- Lint: `.venv/bin/python -m pyflakes core ui main.py config.py`.

## Build
`./build.sh` runs `pyinstaller conductor.spec`, codesigns, builds a DMG with `create-dmg`, and
notarizes it. For a local unsigned bundle only: `.venv/bin/pyinstaller conductor.spec --noconfirm`
(output `dist/Conductor.app`). Keep `main.py` and `config.py` at the repo root: the spec's entry
point is `main.py`, and both `build.sh` and `conductor.spec` `import config` top-level to read
`VERSION`. pyobjc frameworks loaded dynamically (Quartz, AppKit, Vision, ApplicationServices)
are listed in the spec's `hiddenimports`.

## Runtime data
`~/Library/Application Support/Conductor-v3/`:
- `config.json` - identity token, preferences, window geometry, onboarding/feedback flags.
- `history.json` - all chat sessions.
Settings -> Uninstall notifies the server, deletes this folder and resets the app's three macOS
permissions (`tccutil`, scoped to the bundle id), so a reinstall replays the setup screens.
`uninstall.sh` notifies the server and deletes this folder only; it doesn't reset permissions.

## Releasing
Only through the `release-client` skill (bump `VERSION`, build/sign/notarize, publish on
conductor-website, merge to main). Don't run `build.sh`'s sign/notarize steps or push to main by hand.
