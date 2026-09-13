"""HTTP client for the Conductor proxy server.

Chat is relayed through the proxy (which holds the central key); ratings and
profile calls are plain REST. Every request carries a server-minted identity
token as the X-Conductor-Id header. User-facing calls (chat, get_me) register
lazily on first use; fire-and-forget calls skip silently when no token exists
rather than burn a registration slot for a throwaway identity.
"""
import json
import socket
import threading
from typing import Iterator

import httpx

from config import SERVER_BASE_URL
from core import identity


class RegistrationThrottled(Exception):
    """The server is rate limiting new registrations from this IP (HTTP 429).

    Happens on first launch behind a busy shared/CGNAT IP. Transient — the
    user should try again later; nothing is wrong with their install.
    """


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
        # shutdown() before close(): close() alone only drops the fd, and on
        # macOS a recv() blocked in the worker thread keeps blocking after
        # that (found 2026-09-13: the server logged the disconnect at once,
        # the worker sat until the read timeout). SHUT_RDWR wakes the read
        # with EOF. Works on the TLS socket in prod too (SSLSocket.shutdown
        # forwards to the underlying socket).
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


def register() -> str:
    """Mint a fresh identity from the server and persist its token.

    Raises RegistrationThrottled on 429 (per-IP registration cap).
    """
    r = httpx.post(f"{SERVER_BASE_URL}/v3/register", timeout=30)
    if r.status_code == 429:
        raise RegistrationThrottled()
    r.raise_for_status()
    token = r.json()["conductor_id"]
    identity.save_token(token)
    return token


def _ensure_token() -> str:
    """Stored token, or register on first need."""
    return identity.get_token() or register()


def _headers(token: str) -> dict:
    return {"X-Conductor-Id": token, "Content-Type": "application/json"}


def stream_chat(
    text: str,
    history: list[dict] | None,
    screenshots_b64: list[str] | None = None,
    ax_state: str | None = None,
    resume: str | None = None,
    cancel: CancelToken | None = None,
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
    core.ax_capture) — a text dump of currently open Logic windows/dialogs'
    Accessibility state, pushed alongside the screenshots for the same
    reason: exact control values (checkbox state, selected dropdown item,
    a field's real contents) that a screenshot alone can get wrong.

    `resume` is "allow_research" / "deny_research" for the second half of a
    research-confirm turn: `history` is then the transcript the server's
    "research_prompt" event handed back, and `text` is ignored server-side.
    Every request declares research_confirm so the server parks a turn at
    its first web_research call instead of running it.

    `cancel` lets the UI thread abort this call mid-stream (see CancelToken).

    kind is one of:
        "chunk"           -> payload is a str of streamed text
        "status"          -> payload is a str progress notice
        "research_prompt" -> payload is a dict {query, history}; the stream
                             ends here, no "done" follows -- re-call with
                             resume= and that history to finish the turn
        "done"            -> payload is a dict {event_id, tokens_in, tokens_out, history, ...}
        "cancelled"       -> the caller cancelled; nothing else follows
        "error"           -> payload is a str error message

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
                "POST", url, headers=_headers(_ensure_token()),
                json={
                    "message": text,
                    "history": history,
                    "screenshots": screenshots_b64 or None,
                    "ax_state": ax_state,
                    "research_confirm": True,
                    "resume": resume,
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
                    # but keep the server's actual detail in our log: the 422
                    # body names which validator fired, and until 2026-09-09
                    # it was discarded here, leaving a live incident (an
                    # oversized screenshot) to be reconstructed by hand.
                    resp.read()
                    try:
                        detail = resp.json().get("detail")
                    except Exception:
                        detail = resp.text[:500]
                    print(f"[server_client] {resp.status_code} from /v3/chat: {detail}")
                    yield ("error", "That message was too long to send. Try shortening it, or start a new chat.")
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
                    elif kind == "research_prompt":
                        yield ("research_prompt", obj)
                        return
                    elif kind == "error":
                        yield ("error", obj.get("message", "error"))
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
            raise


def _timeout_fallback(history: list[dict] | None) -> Iterator[tuple[str, object]]:
    """See stream_chat's TimeoutException note (2026-09-04)."""
    yield (
        "chunk",
        "The research call I was running timed out, so I wasn't able to "
        "get a confirmed answer for this. From general knowledge alone "
        "I can't verify it — try asking again, or try rephrasing your "
        "question.",
    )
    yield ("done", {"source_tier": "", "sources": [], "history": history})



def post_rating(event_id: str, rating: int) -> None:
    """rating is 1 (thumbs up) or -1 (thumbs down)."""
    token = identity.get_token()
    if token is None:
        return  # never registered — there is no event of ours to rate
    r = httpx.post(
        f"{SERVER_BASE_URL}/v3/ratings",
        headers=_headers(token),
        json={"event_id": event_id, "rating": rating},
        timeout=30,
    )
    r.raise_for_status()


def post_rating_async(event_id: str, rating: int) -> None:
    """Fire-and-forget post_rating on a daemon thread."""
    def _run() -> None:
        try:
            post_rating(event_id, rating)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


def get_me() -> dict:
    """Fetch this user's profile + free-tier usage (free_used, free_limit, remaining)."""
    for attempt in range(2):  # one retry on 401, same rationale as stream_chat
        r = httpx.get(f"{SERVER_BASE_URL}/v3/me", headers=_headers(_ensure_token()), timeout=30)
        if r.status_code == 401 and attempt == 0:
            identity.clear_token()
            continue
        r.raise_for_status()
        return r.json()


def put_me(
    experience: str | None = None,
    role: str | None = None,
) -> None:
    """Upsert onboarding answers."""
    token = identity.get_token()
    if token is None:
        return  # fire-and-forget — don't burn a registration just for this
    body = {
        k: v
        for k, v in {
            "experience": experience,
            "role": role,
        }.items()
        if v is not None
    }
    r = httpx.put(f"{SERVER_BASE_URL}/v3/me", headers=_headers(token), json=body, timeout=30)
    r.raise_for_status()


def put_me_async(**kwargs) -> None:
    """Fire-and-forget put_me on a daemon thread so the UI never blocks on it."""
    def _run() -> None:
        try:
            put_me(**kwargs)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


def delete_me() -> None:
    """Mark this install as uninstalled. Best-effort — never raises."""
    token = identity.get_token()
    if token is None:
        return  # never registered — no server-side user to mark
    try:
        httpx.delete(f"{SERVER_BASE_URL}/v3/me", headers=_headers(token), timeout=5)
    except Exception:
        pass
