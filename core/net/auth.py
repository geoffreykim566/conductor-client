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


class RegistrationRefused(Exception):
    """The waitlist gate refused this Mac (HTTP 403). `reason` is the server's code:
    email_required, not_on_waitlist, not_approved or install_limit."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def register(email: str | None = None, timeout: float = 30) -> str:
    """Mint a fresh identity from the server and persist its token.

    A Mac the server already knows needs no email; a new one needs an approved
    waitlist email. Raises RegistrationThrottled on 429, RegistrationRefused on 403.
    """
    r = httpx.post(f"{SERVER_BASE_URL}/v3/register", headers=_device_header(),
                   json={"email": email} if email else None, timeout=timeout)
    if r.status_code == 429:
        raise RegistrationThrottled()
    if r.status_code == 403:
        try:
            reason = r.json().get("detail") or "email_required"
        except ValueError:
            reason = "email_required"
        raise RegistrationRefused(reason)
    r.raise_for_status()
    token = r.json()["conductor_id"]
    identity.save_token(token)
    return token


def ensure_token() -> str:
    """Stored token, or register on first need."""
    return identity.get_token() or register()


def _device_header() -> dict:
    h = identity.device_hash()
    return {"X-Conductor-Device": h} if h else {}


def headers(token: str) -> dict:
    """Auth headers; the device hash rides along so /v3/me can link a pre-hash user to this Mac."""
    return {"X-Conductor-Id": token, "Content-Type": "application/json", **_device_header()}
