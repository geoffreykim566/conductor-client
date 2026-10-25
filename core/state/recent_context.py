"""The last few turns' AX dumps and the last card's steps, kept in memory for bug reports.

Neither is saved to history.json, so a report can only carry what this run of the app saw.
"""
import threading
import time
from collections import deque

MAX_AX_STATES = 3

_ax: deque[dict] = deque(maxlen=MAX_AX_STATES)
_card: dict | None = None
_lock = threading.Lock()


def note_ax_state(text: str | None, message: str) -> None:
    """Called from the turn's worker thread right after capture."""
    with _lock:
        _ax.append({"label": f"turn at {time.strftime('%H:%M:%S')}: {message[:80]}", "text": text})


def note_card(steps: list) -> None:
    global _card
    with _lock:
        _card = {"at": time.strftime("%H:%M:%S"), "steps": steps}


def ax_states() -> list[dict]:
    with _lock:
        return list(_ax)


def last_card() -> dict | None:
    with _lock:
        return _card


def clear() -> None:
    global _card
    with _lock:
        _ax.clear()
        _card = None
