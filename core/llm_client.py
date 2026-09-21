"""QThread worker that streams a Claude response and emits Qt signals.

Every message is relayed through the Conductor proxy, which holds the central
key and enforces the message cap. A 402 fires `limit_reached`.
"""
from PySide6.QtCore import QThread, Signal

from core import ax_capture, window_capture
from core.server_client import CancelToken, FreeLimitReached, RegistrationThrottled, get_me, stream_chat


class StreamWorker(QThread):
    """Worker that streams an Anthropic response via the Conductor proxy.

    Signals:
        chunk(str)                           — emitted for each piece of text streamed in
        status(str)                          — transient research-progress notice
        done(str, int, str, object, object, object, bool)  — (event_id, remaining,
                                                            source_tier, sources,
                                                            walkthrough_steps, history,
                                                            auto_run)
        research_prompt(str, object)         — server parked the turn at a web_research
                                               call: (query, history). No done follows;
                                               start a new worker with resume= and that
                                               history to finish the turn.
        cancelled()                          — cancel() was called; nothing else follows
        error(str)                           — emitted with an error message on failure
        limit_reached(int)                   — message cap reached (arg is the cap, or -1 if unknown)
    """

    chunk = Signal(str)
    status = Signal(str)
    done = Signal(str, int, str, object, object, object, bool)
    research_prompt = Signal(str, object)
    cancelled = Signal()
    error = Signal(str)
    limit_reached = Signal(int)

    def __init__(self, text: str, history: list[dict] | None, resume: str | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self._history = history
        self._resume = resume
        self._cancel = CancelToken()

    def cancel(self) -> None:
        """Abort this turn from the UI thread (Esc). Safe to call at any point,
        including before the request has opened; `cancelled` is emitted once
        the thread notices, and no done/error follows it."""
        self._cancel.cancel()

    def run(self) -> None:
        event_id = ""
        remaining = -1
        source_tier = ""
        sources: list = []
        walkthrough_steps: list = []
        history = None
        auto_run = False
        # Pushed silently, like AX state -- no user-facing toggle, no attachment
        # UI. Best-effort: Logic not running / no Screen Recording permission
        # just means an empty list, never something a turn should block on.
        try:
            screenshots_b64 = window_capture.capture_context_images_b64()
        except Exception:
            screenshots_b64 = []
        try:
            ax_state = ax_capture.capture_ax_state()
        except Exception:
            ax_state = None
        if self._cancel.is_cancelled():  # Esc during the captures above
            self.cancelled.emit()
            return
        try:
            for kind, payload in stream_chat(
                self._text, self._history, screenshots_b64, ax_state,
                resume=self._resume, cancel=self._cancel,
            ):
                if kind == "chunk":
                    self.chunk.emit(payload)
                elif kind == "status":
                    self.status.emit(payload)
                elif kind == "research_prompt":
                    self.research_prompt.emit(payload.get("query", ""), payload.get("history"))
                    return
                elif kind == "cancelled":
                    self.cancelled.emit()
                    return
                elif kind == "done":
                    event_id = payload.get("event_id", "")
                    remaining = payload.get("remaining", -1)
                    source_tier = payload.get("source_tier", "")
                    sources = payload.get("sources") or []
                    walkthrough_steps = payload.get("walkthrough_steps") or []
                    history = payload.get("history")
                    # Server's per-turn call: may this card run without Run
                    # (an instruction, not a question or bulk request)? Absent
                    # from older servers -> False, i.e. always ask.
                    auto_run = bool(payload.get("auto_run"))
                elif kind == "error":
                    self.error.emit(str(payload))
                    return
            self.done.emit(event_id, remaining, source_tier, sources,
                           walkthrough_steps, history, auto_run)
        except FreeLimitReached as e:
            self.limit_reached.emit(e.limit if e.limit is not None else -1)
        except RegistrationThrottled:
            # First launch from a busy shared IP — transient, not the user's fault.
            self.error.emit("Couldn't set up your free account right now. Please try again later.")
        except Exception as e:
            if self._cancel.is_cancelled():
                self.cancelled.emit()
                return
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
