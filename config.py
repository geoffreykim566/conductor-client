"""App-wide constants: version, data dir, server URL, capture limits.

Stays at the repo root: build.sh and conductor.spec import it as top-level `config`.
"""
import os
from pathlib import Path

VERSION = "0.4.1"

# --- App data ---
# Own directory, separate from the legacy v1 app's "Conductor" dir, so the two
# never share an identity token, chat history, or window state.
APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "Conductor-v3"

# --- Server (proxy backend) ---
# Real deployed server-v3 API. Override CONDUCTOR_SERVER_URL for local dev
# against a docker-compose server-v3 instance instead.
SERVER_BASE_URL = os.environ.get("CONDUCTOR_SERVER_URL", "https://api.askconductor.ai")

# --- Updates ---
# DMG releases (GitHub Releases) and the marketing page live in conductor-website.
GITHUB_REPO = "geoffreykim566/conductor-website"
WEBSITE_URL = "https://askconductor.ai"

# --- Feedback ---
FEEDBACK_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdFXMtLksRH-BfQ92vm6nQJKtupz2Nm8LZgBczXiOhZwMCt9A/viewform?usp=dialog"
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
# Mirror of server-v3 api.py's _MAX_SCREENSHOT_CHARS. Anything still over it
# after JPEG encoding is skipped client-side rather than sent to be dropped.
MAX_SCREENSHOT_B64_CHARS = 2 * 1024 * 1024
