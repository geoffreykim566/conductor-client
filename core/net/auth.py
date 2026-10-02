"""Server-minted identity token: register lazily, and build the auth header.

User-facing calls (chat, get_me) register on first use; fire-and-forget calls
skip silently when no token exists rather than burn a registration slot.
"""
import httpx

from config import SERVER_BASE_URL
from core.state import identity


class RegistrationThrottled(Exception):
    """The server is rate limiting new registrations from this IP (HTTP 429).

    Happens on first launch behind a busy shared/CGNAT IP. Transient — the
    user should try again later; nothing is wrong with their install.
    """


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


def ensure_token() -> str:
    """Stored token, or register on first need."""
    return identity.get_token() or register()


def headers(token: str) -> dict:
    return {"X-Conductor-Id": token, "Content-Type": "application/json"}
