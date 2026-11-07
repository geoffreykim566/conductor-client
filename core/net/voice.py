"""POST /v3/transcribe: one phrase (WAV) to text, within the daily voice limit; and its worker."""
import base64

import httpx
from PySide6.QtCore import QThread, Signal

from config import SERVER_BASE_URL
from core.net.auth import ensure_token, headers
from core.state import identity


class VoiceLimitReached(Exception):
    def __init__(self, resets_at: str | None) -> None:
        super().__init__("voice limit reached")
        self.resets_at = resets_at


class TranscribeFailed(Exception):
    """kind: offline | down | busy | retry (as the chat errors); code: the HTTP status, if any."""

    def __init__(self, kind: str, code: int | None = None) -> None:
        super().__init__(f"transcribe failed: {kind} {code}")
        self.kind, self.code = kind, code


def transcribe(wav: bytes, context: str = "") -> dict:
    """{text, seconds_left, resets_at}. Raises VoiceLimitReached or TranscribeFailed."""
    body = {"audio": base64.b64encode(wav).decode(), "context": context[-4000:]}
    for attempt in range(2):   # one retry on 401, as get_me
        try:
            r = httpx.post(f"{SERVER_BASE_URL}/v3/transcribe", headers=headers(ensure_token()),
                           json=body, timeout=40)
        except httpx.ConnectError as e:
            raise TranscribeFailed("offline") from e
        except httpx.HTTPError as e:
            raise TranscribeFailed("retry") from e
        if r.status_code == 401 and attempt == 0:
            identity.clear_token()
            continue
        break
    if r.status_code == 200:
        return r.json()
    data = _json(r)
    if r.status_code == 402:
        raise VoiceLimitReached(data.get("resets_at"))
    if r.status_code == 429:
        raise TranscribeFailed("busy", 429)
    if r.status_code in (502, 503):
        raise TranscribeFailed(data.get("kind") or "down", data.get("code") or r.status_code)
    raise TranscribeFailed("retry", r.status_code)


def _json(r: httpx.Response) -> dict:
    try:
        d = r.json()
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


class TranscribeWorker(QThread):
    """One phrase off the UI thread.

    Signals:
        done(str, int, str)  -- (text, seconds_left, resets_at)
        limit(str)           -- the daily limit was reached (resets_at)
        failed(str, object)  -- (kind, code or None)
    """

    done = Signal(str, int, str)
    limit = Signal(str)
    failed = Signal(str, object)

    def __init__(self, wav: bytes, context: str, parent=None) -> None:
        super().__init__(parent)
        self._wav, self._context = wav, context

    def run(self) -> None:
        try:
            r = transcribe(self._wav, self._context)
            self.done.emit(r.get("text") or "", int(r.get("seconds_left", -1)), r.get("resets_at") or "")
        except VoiceLimitReached as e:
            self.limit.emit(e.resets_at or "")
        except TranscribeFailed as e:
            print(f"[voice] transcribe failed: {e}", flush=True)
            self.failed.emit(e.kind, e.code)
        except Exception as e:
            print(f"[voice] transcribe error: {e!r}", flush=True)
            self.failed.emit("retry", None)
