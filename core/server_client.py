"""HTTP client for the Conductor proxy server.

Chat is relayed through the proxy (which holds the central key); ratings and
profile calls are plain REST. Every request carries a server-minted identity
token as the X-Conductor-Id header. User-facing calls (chat, get_me) register
lazily on first use; fire-and-forget calls skip silently when no token exists
rather than burn a registration slot for a throwaway identity.
"""
import json
import threading
import time
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


def register() -> str:
    """Mint a fresh identity from the server and persist its token.

    Raises RegistrationThrottled on 429 (per-IP registration cap).
    """
    r = httpx.post(f"{SERVER_BASE_URL}/v1/register", timeout=30)
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


def stream_chat(messages: list[dict]) -> Iterator[tuple[str, object]]:
    """Relay a chat and yield (kind, payload) as the proxy streams.

    kind is one of:
        "chunk" -> payload is a str of streamed text
        "done"  -> payload is a dict {event_id, tokens_in, tokens_out}
        "error" -> payload is a str error message

    Raises FreeLimitReached on 402 when the message cap is hit, and
    RegistrationThrottled if a needed registration is rate limited.
    """
    url = f"{SERVER_BASE_URL}/v1/chat"
    # Exactly one retry on 401: the token was rejected (e.g. the server's
    # signing secret rotated), so re-register once. A loop, not recursion —
    # a misconfigured server must not turn every client into a register storm.
    for attempt in range(2):
        with httpx.stream(
            "POST", url, headers=_headers(_ensure_token()),
            json={"messages": messages}, timeout=120,
        ) as resp:
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
                # Surface a clean message instead of a raw HTTPStatusError.
                resp.read()
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
                elif kind == "error":
                    yield ("error", obj.get("message", "error"))
            return


def post_rating(event_id: str, rating: int) -> None:
    """rating is 1 (thumbs up) or -1 (thumbs down)."""
    token = identity.get_token()
    if token is None:
        return  # never registered — there is no event of ours to rate
    r = httpx.post(
        f"{SERVER_BASE_URL}/v1/ratings",
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
        r = httpx.get(f"{SERVER_BASE_URL}/v1/me", headers=_headers(_ensure_token()), timeout=30)
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
    r = httpx.put(f"{SERVER_BASE_URL}/v1/me", headers=_headers(token), json=body, timeout=30)
    r.raise_for_status()


def put_me_async(**kwargs) -> None:
    """Fire-and-forget put_me on a daemon thread so the UI never blocks on it."""
    def _run() -> None:
        try:
            put_me(**kwargs)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


_control_map_cache: dict | None = None
_control_map_fetched_at: float = 0.0
_CONTROL_MAP_TTL = 3600.0


def fetch_control_map() -> dict | None:
    """Return {entries, chrome} from the server, cached for 1 hour.

    Returns the stale cache on network error so the locate pipeline keeps
    working when the server is temporarily unreachable. Returns None only
    on the very first call when no cache exists yet and the request fails.
    """
    global _control_map_cache, _control_map_fetched_at
    if (_control_map_cache is not None
            and time.monotonic() - _control_map_fetched_at < _CONTROL_MAP_TTL):
        return _control_map_cache
    try:
        r = httpx.get(f"{SERVER_BASE_URL}/v1/control-map", timeout=10)
        r.raise_for_status()
        _control_map_cache = r.json()
        _control_map_fetched_at = time.monotonic()
    except Exception:
        pass  # return stale cache (or None on first-call failure)
    return _control_map_cache


def delete_me() -> None:
    """Mark this install as uninstalled. Best-effort — never raises."""
    token = identity.get_token()
    if token is None:
        return  # never registered — no server-side user to mark
    try:
        httpx.delete(f"{SERVER_BASE_URL}/v1/me", headers=_headers(token), timeout=5)
    except Exception:
        pass
