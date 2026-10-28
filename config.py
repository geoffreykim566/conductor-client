"""App-wide constants: version, data dir, server URL, capture limits.

Stays at the repo root: build.sh and conductor.spec import it as top-level `config`.
"""
import json
import os
from pathlib import Path

VERSION = "0.4.3"

# --- App data ---
# "Conductor", unless another app's data is already there (see core/state/data_dir.py,
# which moves the old "Conductor-v3" dir in at launch).
_APP_SUPPORT_ROOT = Path.home() / "Library" / "Application Support"
DATA_DIR_MARKER = ".conductor-logicpro"
LEGACY_APP_SUPPORT_DIR = _APP_SUPPORT_ROOT / "Conductor-v3"
FALLBACK_APP_SUPPORT_DIR = _APP_SUPPORT_ROOT / "com.conductor.logicpro"


def is_our_data_dir(path: Path) -> bool:
    """True if `path` holds this app's data: our marker, or a config.json with our
    token (pre-v3 builds and Conductor-v3 had no marker)."""
    if (path / DATA_DIR_MARKER).exists():
        return True
    try:
        return "conductor_token" in json.loads((path / "config.json").read_text())
    except Exception:
        return False


def resolve_app_support_dir(preferred: Path, fallback: Path) -> Path:
    """`preferred` unless something that isn't ours already lives there."""
    if preferred.exists() and not is_our_data_dir(preferred):
        return fallback
    return preferred


APP_SUPPORT_DIR = resolve_app_support_dir(_APP_SUPPORT_ROOT / "Conductor", FALLBACK_APP_SUPPORT_DIR)

# --- Server (proxy backend) ---
# Real deployed server API. Override CONDUCTOR_SERVER_URL for local dev
# against a docker-compose server instance instead.
SERVER_BASE_URL = os.environ.get("CONDUCTOR_SERVER_URL", "https://api.askconductor.ai")

# --- Updates ---
# DMG releases (GitHub Releases) and the marketing page live in conductor-website.
GITHUB_REPO = "geoffreykim566/conductor-website"
WEBSITE_URL = "https://askconductor.ai"
PRIVACY_URL = f"{WEBSITE_URL}/privacy"

# --- Feedback ---
FEEDBACK_PROMPT_REMAINING_THRESHOLDS = (35, 20, 0)

# Window geometry and all other UI tokens live in ui/theme.py.

# --- Capture ---
# Owning-application names as reported by Quartz CGWindowListCopyWindowInfo.
LOGIC_PRO_APP_NAMES = ("Logic Pro", "Logic Pro X")
MAX_IMAGE_LONG_EDGE = 1568  # Claude vision sweet spot
# Windows are captured one by one (see core/capture/README.md "Per-window
# capture"); capped so many open plugin windows don't balloon vision tokens.
MAX_CONTEXT_WINDOWS = 4
# JPEG, not PNG (see core/capture/README.md "JPEG screenshots"). Stay >= 70
# to keep small scale text crisp.
SCREENSHOT_JPEG_QUALITY = 80
# Mirror of server api.py's _MAX_SCREENSHOT_CHARS. Anything still over it
# after JPEG encoding is skipped client-side rather than sent to be dropped.
MAX_SCREENSHOT_B64_CHARS = 2 * 1024 * 1024
