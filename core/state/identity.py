"""This install's identity: the server-minted token in config.json, and a hash of the Mac's hardware UUID.

The token (`<uuid>.<sig>`) is minted by the server via POST /v3/register and
is opaque here — this module only persists it. Legacy `device_id` entries
from pre-token builds are ignored: they are unsigned, so the server would
reject them anyway.
"""
import functools
import hashlib
import re
import subprocess

from core.state.config_store import read_config, write_config


@functools.cache
def device_hash() -> str | None:
    """SHA-256 of this Mac's IOPlatformUUID (never sent raw), or None if it can't be read.

    The server keys users on it, so a reinstall (Uninstall wipes the token) is the same user.
    """
    try:
        out = subprocess.run(["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r'"IOPlatformUUID" = "([0-9A-Fa-f-]{36})"', out)
    return hashlib.sha256(f"conductor-device:{m.group(1).upper()}".encode()).hexdigest() if m else None


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
