"""Per-install identity token, stored in config.json.

The token (`<uuid>.<sig>`) is minted by the server via POST /v3/register and
is opaque here — this module only persists it. Legacy `device_id` entries
from pre-token builds are ignored: they are unsigned, so the server would
reject them anyway.
"""
from core.state.config_store import read_config, write_config


def get_token() -> str | None:
    """Return the stored conductor token, or None if never registered."""
    return read_config().get("conductor_token") or None


def save_token(token: str) -> None:
    data = read_config()
    data["conductor_token"] = token
    write_config(data)


def clear_token() -> None:
    """Drop the stored token (server rejected it, e.g. after a secret rotation)."""
    data = read_config()
    if data.pop("conductor_token", None) is not None:
        write_config(data)
