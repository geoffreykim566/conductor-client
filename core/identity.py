"""Per-install identity token, stored in config.json.

The token (`<uuid>.<sig>`) is minted by the server via POST /v3/register and
is opaque here — this module only persists it. Legacy `device_id` entries
from pre-token builds are ignored: they are unsigned, so the server would
reject them anyway.
"""
import json

from config import APP_SUPPORT_DIR

_CONFIG_PATH = APP_SUPPORT_DIR / "config.json"


def _read_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_config(data: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data, indent=2))


def get_token() -> str | None:
    """Return the stored conductor token, or None if never registered."""
    return _read_config().get("conductor_token") or None


def save_token(token: str) -> None:
    data = _read_config()
    data["conductor_token"] = token
    _write_config(data)


def clear_token() -> None:
    """Drop the stored token (server rejected it, e.g. after a secret rotation)."""
    data = _read_config()
    if data.pop("conductor_token", None) is not None:
        _write_config(data)
