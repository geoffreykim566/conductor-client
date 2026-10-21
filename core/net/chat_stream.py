"""Stream one chat turn from POST /v3/chat as (kind, payload) events."""
import json
import socket
import threading
from typing import Iterator

import httpx

from config import SERVER_BASE_URL
from core.net.auth import ensure_token, headers
from core.state import identity


# What the user is told when a turn fails; the cause is only printed. `kind` comes from the
# server's error event, or from the status / connection failure here (README: Errors).
ERROR_TEXT = {
    "offline": "Couldn't reach Conductor. Check your internet connection; if it's working, Conductor may be down.",
    "down": "Conductor is down right now. Please try again later.",
    "busy": "Too many messages at once. Please wait a minute and try again.",
    "retry": "Something went wrong on Conductor's end. Please try again in a minute.",
}


def error_text(kind: str, code: int | None = None) -> str:
    """'[Error 429] Too many messages…': the native HTTP status when there is one."""
    return f"[Error{f' {code}' if code else ''}] {ERROR_TEXT[kind]}"


class FreeLimitReached(Exception):
    """Raised when the proxy rejects a chat for exceeding the message cap (HTTP 402).

    `limit` carries the server's message cap (from FREE_LIMIT in the server
    env) when the 402 body includes it, else None.
    """

    def __init__(self, limit: int | None = None) -> None:
        super().__init__("free limit reached")
        self.limit = limit


class CancelToken:
    """Cross-thread cancel handle for one stream_chat() call.

    The worker thread blocks inside httpx reading SSE lines; the only way to
    unblock it promptly from the UI thread is to close the response's
    underlying stream, which makes that read raise. `cancel()` does both:
    flags the token (so the reader knows the raise was ours, not a network
    fault) and closes the response if one is open yet. Dropping the
    connection is also what tells the server to abort the turn (api.py's
    [turn_cancelled] path) -- there's no separate cancel request.
    """

    def __init__(self) -> None:
        self._flag = threading.Event()
        self.response: httpx.Response | None = None

    def cancel(self) -> None:
        self._flag.set()
        resp = self.response
        if resp is None:
            return
        # shutdown() before close(): on macOS close() alone leaves a blocked
        # recv() blocking until the read timeout (see README "Cancelling a
        # stream"); SHUT_RDWR wakes it with EOF, on the TLS socket too.
        try:
            stream = resp.extensions.get("network_stream")
            sock = stream.get_extra_info("socket") if stream is not None else None
            if sock is not None:
                sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            resp.close()
        except Exception:
            pass

    def is_cancelled(self) -> bool:
        return self._flag.is_set()


def stream_chat(
    text: str,
    history: list[dict] | None,
    screenshots_b64: list[str] | None = None,
    ax_state: str | None = None,
    resume: str | None = None,
    cancel: CancelToken | None = None,
    plugin_values: dict | None = None,
) -> Iterator[tuple[str, object]]:
    """Relay one new user turn and yield (kind, payload) as the proxy streams.

    `history` is opaque — exactly what a prior call's "done" payload carried
    as "history" (None to start a fresh conversation) — round-tripped as-is
    so the server can keep multi-turn continuity without pinning any state
    of its own between requests.

    `screenshots_b64` is fresh, per-request visual context (base64 PNGs, one
    per captured Logic Pro window) — never part of `history`. The server
    only ever uses it for this turn's model calls and doesn't echo it back,
    so screenshots aren't resent on every later turn.

    `ax_state` is the same kind of fresh, per-turn-only context (see
    core.ax.state_capture) — a text dump of currently open Logic windows/dialogs'
    Accessibility state, pushed alongside the screenshots for the same
    reason: exact control values (checkbox state, selected dropdown item,
    a field's real contents) that a screenshot alone can get wrong.

    `resume` is "allow_research" / "deny_research" for the second half of a
    research-confirm turn: `history` is then the transcript the server's
    "research_prompt" event handed back, and `text` is ignored server-side.
    Every request declares research_confirm so the server parks a turn at
    its first web_research call instead of running it, and plugin_reads so it
    may park at read_plugin_values: "allow_plugin_read" then carries what the
    client read as `plugin_values` (core.automation.plugin_read).

    `cancel` lets the UI thread abort this call mid-stream (see CancelToken).

    kind is one of:
        "chunk"           -> payload is a str of streamed text
        "status"          -> payload is a str progress notice
        "research_prompt" -> payload is a dict {query, history}; the stream
                             ends here, no "done" follows -- re-call with
                             resume= and that history to finish the turn
        "plugin_read_prompt" -> payload is a dict {plugin, track, history}; the
                             same, resumed with allow/deny_plugin_read
        "done"            -> payload is a dict {event_id, tokens_in, tokens_out, history, ...}
        "cancelled"       -> the caller cancelled; nothing else follows
        "error"           -> payload is the str to show the user (error_text)

    Raises FreeLimitReached on 402 when the message cap is hit, and
    RegistrationThrottled if a needed registration is rate limited.
    """
    url = f"{SERVER_BASE_URL}/v3/chat"
    # Exactly one retry on 401: the token was rejected (e.g. the server's
    # signing secret rotated), so re-register once. A loop, not recursion —
    # a misconfigured server must not turn every client into a register storm.
    for attempt in range(2):
        if cancel is not None and cancel.is_cancelled():
            yield ("cancelled", None)
            return
        try:
            with httpx.stream(
                "POST", url, headers=headers(ensure_token()),
                json={
                    "message": text,
                    "history": history,
                    "screenshots": screenshots_b64 or None,
                    "ax_state": ax_state,
                    "research_confirm": True,
                    "plugin_reads": True,
                    "resume": resume,
                    "plugin_values": plugin_values,
                },
                timeout=120,
            ) as resp:
                if cancel is not None:
                    cancel.response = resp
                    if cancel.is_cancelled():  # raced: cancelled while connecting
                        yield ("cancelled", None)
                        return
                if resp.status_code == 401 and attempt == 0:
                    identity.clear_token()
                    continue
                if resp.status_code == 402:
                    limit = None
                    try:
                        resp.read()  # body isn't read implicitly on a streaming response
                        detail = resp.json().get("detail")
                        if isinstance(detail, dict):
                            limit = detail.get("limit")
                    except Exception:
                        pass
                    raise FreeLimitReached(limit)
                if resp.status_code in (413, 422):
                    # Oversized / rejected body — e.g. a single message past the
                    # server's length cap, which the rolling window can't trim away.
                    # Surface a clean message instead of a raw HTTPStatusError,
                    # but keep the server's detail in our log: the 422 body
                    # names which validator fired.
                    resp.read()
                    try:
                        detail = resp.json().get("detail")
                    except Exception:
                        detail = resp.text[:500]
                    print(f"[server_client] {resp.status_code} from /v3/chat: {detail}")
                    yield ("error", f"[Error {resp.status_code}] That message was too long to send. "
                                    "Try shortening it, or start a new chat.")
                    return
                if resp.status_code in (429, 503):
                    # 429: the server's per-IP rate limit; 503: its daily budget breaker.
                    resp.read()
                    print(f"[server_error] {resp.status_code} from /v3/chat: {resp.text[:500]}")
                    yield ("error", error_text("busy" if resp.status_code == 429 else "down", resp.status_code))
                    return
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    obj = json.loads(line[len("data: "):])
                    kind = obj.get("type")
                    if kind == "chunk":
                        yield ("chunk", obj.get("text", ""))
                    elif kind == "done":
                        yield ("done", obj)
                    elif kind == "status":
                        yield ("status", obj.get("text", ""))
                    elif kind in ("research_prompt", "plugin_read_prompt"):
                        yield (kind, obj)
                        return
                    elif kind == "error":
                        # An older server sends only a raw `message`: print it, show "retry".
                        print(f"[server_error] {obj}")
                        kind = obj.get("kind") if obj.get("kind") in ERROR_TEXT else "retry"
                        yield ("error", error_text(kind, obj.get("code")))
                return
        except Exception as e:
            # Our own cancel closes the stream out from under the read above,
            # which surfaces as whichever closed-stream error httpx/httpcore
            # raise -- report it as a cancel, not a failure. Anything else
            # falls through to the handlers below / the caller.
            if cancel is not None and cancel.is_cancelled():
                yield ("cancelled", None)
                return
            if isinstance(e, httpx.TimeoutException):
                yield from _timeout_fallback(history)
                return
            if isinstance(e, httpx.ConnectError):  # offline, or the server is down
                print(f"[server_error] {type(e).__name__}: {e}")
                yield ("error", error_text("offline"))
                return
            raise


def _timeout_fallback(history: list[dict] | None) -> Iterator[tuple[str, object]]:
    """Stand-in turn when /v3/chat times out: a canned reply, history unchanged."""

    yield (
        "chunk",
        "The research call I was running timed out, so I wasn't able to "
        "get a confirmed answer for this. From general knowledge alone "
        "I can't verify it — try asking again, or try rephrasing your "
        "question.",
    )
    yield ("done", {"sources": [], "history": history})
