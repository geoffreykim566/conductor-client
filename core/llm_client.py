"""QThread worker that streams a Claude response and emits Qt signals.

Every message is relayed through the Conductor proxy, which holds the central
key and enforces the message cap. A 402 fires `limit_reached`.
"""
from PySide6.QtCore import QThread, Signal

from core.server_client import FreeLimitReached, RegistrationThrottled, get_me, stream_chat


class StreamWorker(QThread):
    """Worker that streams an Anthropic response via the Conductor proxy.

    Signals:
        chunk(str)                           — emitted for each piece of text streamed in
        status(str)                          — transient research-progress notice
        done(str, int, str, object, str, str, object)  — (event_id, remaining, source_tier,
                                                            sources, locate_type, element,
                                                            walkthrough_steps)
        error(str)                           — emitted with an error message on failure
        limit_reached(int)                   — message cap reached (arg is the cap, or -1 if unknown)
    """

    chunk = Signal(str)
    status = Signal(str)
    done = Signal(str, int, str, object, str, str, object)
    error = Signal(str)
    limit_reached = Signal(int)

    def __init__(self, messages: list[dict], parent=None) -> None:
        super().__init__(parent)
        self._messages = messages

    def run(self) -> None:
        event_id = ""
        remaining = -1
        source_tier = ""
        sources: list = []
        walkthrough_steps: list = []
        try:
            for kind, payload in stream_chat(self._messages):
                if kind == "chunk":
                    self.chunk.emit(payload)
                elif kind == "status":
                    self.status.emit(payload)
                elif kind == "done":
                    event_id = payload.get("event_id", "")
                    remaining = payload.get("remaining", -1)
                    source_tier = payload.get("source_tier", "")
                    sources = payload.get("sources") or []
                    locate_type = payload.get("locate_type", "")
                    element = payload.get("element", "")
                    search_term = payload.get("search_term", "")
                    walkthrough_steps = payload.get("walkthrough_steps") or []
                elif kind == "error":
                    self.error.emit(str(payload))
                    return
            # Use element if present; fall back to first word of search_term so
            # navigation queries without a named element still get a locate target.
            intent = payload.get("intent", "")
            locate_target = element or (search_term.split()[0] if search_term else "")
            print(f"[classify] intent={intent!r} element={element!r} search_term={search_term!r}", flush=True)
            self.done.emit(event_id, remaining, source_tier, sources,
                           locate_type, locate_target, walkthrough_steps)
        except FreeLimitReached as e:
            self.limit_reached.emit(e.limit if e.limit is not None else -1)
        except RegistrationThrottled:
            # First launch from a busy shared IP — transient, not the user's fault.
            self.error.emit("Couldn't set up your free account right now. Please try again later.")
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")


class MeWorker(QThread):
    """One-shot worker that fetches the user's free-tier usage on a background thread.

    Signals:
        loaded(int) — emitted with messages remaining on success (-1 on failure)
    """

    loaded = Signal(int)

    def run(self) -> None:
        try:
            data = get_me()
            self.loaded.emit(data.get("remaining", -1))
        except Exception:
            self.loaded.emit(-1)
