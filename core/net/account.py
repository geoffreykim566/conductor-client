"""Plain REST calls about this install: ratings, profile/usage, onboarding answers, uninstall."""
import threading

import httpx

from config import SERVER_BASE_URL
from core.net.auth import ensure_token, headers
from core.state import identity


def post_rating(event_id: str, rating: int) -> None:
    """rating is 1 (thumbs up) or -1 (thumbs down)."""
    token = identity.get_token()
    if token is None:
        return  # never registered — there is no event of ours to rate
    r = httpx.post(
        f"{SERVER_BASE_URL}/v3/ratings",
        headers=headers(token),
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
        r = httpx.get(f"{SERVER_BASE_URL}/v3/me", headers=headers(ensure_token()), timeout=30)
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
    r = httpx.put(f"{SERVER_BASE_URL}/v3/me", headers=headers(token), json=body, timeout=30)
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
        httpx.delete(f"{SERVER_BASE_URL}/v3/me", headers=headers(token), timeout=5)
    except Exception:
        pass
