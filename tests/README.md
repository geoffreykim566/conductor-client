# tests

Two kinds of tests, kept apart because only one of them is safe to run anywhere.

## Files
- `unit/` - pytest tests of pure logic; no Logic Pro, no permissions, no network. Run these always.
- `ax_mechanics/` - live scripts that drive a running Logic Pro through AX and synthetic input.

## How it works
`pytest.ini` at the repo root sets `testpaths = tests/unit` and `pythonpath = .`, so a bare
`.venv/bin/python -m pytest` runs only the unit tests. The live scripts are plain modules you run
one at a time: `PYTHONUNBUFFERED=1 .venv/bin/python -m tests.ax_mechanics.<test>`.

## Quirks & why
### Live scripts are not pytest tests
They click and type into whatever Logic project is open, change it, and need Accessibility,
Input Monitoring and Screen Recording granted to the Python that runs them. Their files are
named `t<N>_*.py`, not `test_*.py`, so pytest never collects them.

## Adding tests
Pure function or state module -> `tests/unit/test_<area>.py`. Anything that must touch Logic ->
a new `tests/ax_mechanics/t<N>_<what>.py` built on `_ax_common.py`, with the result recorded in
`tests/ax_mechanics/RESULTS.md`.
