"""Configuration: constants and system prompt. API key is read from APP_SUPPORT_DIR/config.json at runtime."""
import os
from pathlib import Path

VERSION = "0.2.6"

# --- App data ---
# Own directory, separate from the shipping v1 app's "Conductor" dir, so v3
# dev runs never read/write v1's production identity token, chat history, or
# window state.
APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "Conductor-v3"

# --- Server (proxy backend) ---
# TODO: points at local server-v3 for dev. Once server-v3 has a real deployed
# API, change this default back to that URL (not v1's api.askconductor.ai).
SERVER_BASE_URL = os.environ.get("CONDUCTOR_SERVER_URL", "http://127.0.0.1:8000")

# --- Updates ---
# DMG releases and the marketing page both moved to conductor-website (see
# that repo's commit "Update download link for Conductor DMG file" and its
# README/wrangler.jsonc for the askconductor.ai domain) -- these used to
# point at v1's old repo/GitHub Pages URL.
GITHUB_REPO = "geoffreykim566/conductor-website"
WEBSITE_URL = "https://askconductor.ai"

# --- Feedback ---
FEEDBACK_FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdFXMtLksRH-BfQ92vm6nQJKtupz2Nm8LZgBczXiOhZwMCt9A/viewform?usp=dialog"
FEEDBACK_PROMPT_REMAINING_THRESHOLDS = (35, 20, 0)

# --- Window ---
WINDOW_WIDTH = 420
WINDOW_HEIGHT = 500
WINDOW_MARGIN = 20         # distance from screen edge
MINIMIZED_SIZE = 60        # px square for collapsed bubble
MIN_WINDOW_WIDTH = 300
MIN_WINDOW_HEIGHT = 380
MAX_WINDOW_WIDTH = 700
MAX_WINDOW_HEIGHT = 1000

# --- Capture ---
# Owning-application names as reported by Quartz CGWindowListCopyWindowInfo.
LOGIC_PRO_APP_NAMES = ("Logic Pro", "Logic Pro X")
