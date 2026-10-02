@README.md

## Hard rules
- Tests go in `tests/unit` (pytest, pure logic) or `tests/ax_mechanics` (live Logic scripts, never collected by pytest).
- Import direction is `core/events` <- `core/ax`, `core/capture` <- `core/automation`; `core/state` <- `core/net`; `ui` on top. Never import upward from `core/events` or `core/ax` primitives, and no function-level imports to dodge a cycle.
- `main.py` and `config.py` stay at the repo root (`conductor.spec` and `build.sh` import `config` top-level).
- One concern per module; when you add or move a file, update that folder's README `## Files`.
- Dated incident history goes in the folder README's "Quirks & why", not in code comments.
- Releases only via the `release-client` skill; never push or merge to main otherwise.
- Use `.venv/bin/python`; run `pytest` and `pyflakes core ui main.py config.py` before committing.
