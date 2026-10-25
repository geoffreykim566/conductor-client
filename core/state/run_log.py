"""In-memory tail of everything the app prints, for bug reports.

install() tees stdout/stderr into a ring buffer. The packaged app has no console
(sys.stdout is None there), so this buffer is its only log.
"""
import sys
import threading
import time
from collections import deque

MAX_LINES = 2000

_lines: deque[str] = deque(maxlen=MAX_LINES)
_lock = threading.Lock()


class _Tee:
    def __init__(self, stream) -> None:
        self._stream = stream
        self._partial = ""

    def write(self, s: str) -> int:
        if self._stream is not None:
            try:
                self._stream.write(s)
            except Exception:
                pass
        with _lock:
            text = self._partial + s
            *done, self._partial = text.split("\n")
            stamp = time.strftime("%H:%M:%S")
            _lines.extend(f"{stamp} {line}" for line in done)
        return len(s)

    def flush(self) -> None:
        if self._stream is not None:
            try:
                self._stream.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        return False


def install() -> None:
    if not isinstance(sys.stdout, _Tee):
        sys.stdout = _Tee(sys.stdout)
    if not isinstance(sys.stderr, _Tee):
        sys.stderr = _Tee(sys.stderr)


def tail() -> str:
    with _lock:
        return "\n".join(_lines)
