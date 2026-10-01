"""Configuration: constants and system prompt. API key is read from APP_SUPPORT_DIR/config.json at runtime."""
import os
from pathlib import Path

VERSION = "0.4.0"

# --- App data ---
# Own directory, separate from the shipping v1 app's "Conductor" dir, so v3
# dev runs never read/write v1's production identity token, chat history, or
# window state.
APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "Conductor-v3"

# --- Server (proxy backend) ---
# Real deployed server-v3 API. Override CONDUCTOR_SERVER_URL for local dev
# against a docker-compose server-v3 instance instead.
SERVER_BASE_URL = os.environ.get("CONDUCTOR_SERVER_URL", "https://api.askconductor.ai")

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

# Window geometry and all other UI tokens live in ui/theme.py.

# --- Capture ---
# Owning-application names as reported by Quartz CGWindowListCopyWindowInfo.
LOGIC_PRO_APP_NAMES = ("Logic Pro", "Logic Pro X")
MAX_IMAGE_LONG_EDGE = 1568  # Claude vision sweet spot (matches v1's config.py)
# Per-window capture (not v1's single union-rect composite -- that has a
# documented, unresolved bug: when a plugin editor sits on a different
# display than the main window, the union bounding rect spans a huge sparse
# canvas and visual context degrades; see .old-drafts-planning-docs/
# v0.3-phase1-revised-build-log.md's "C2" item). Capturing each window
# separately is immune to that (same reasoning as v1's per-window OCR locate
# path) and shows plugin editors at native clarity instead of shrunk into a
# shared canvas. Capped so a session with many plugin windows open doesn't
# balloon vision tokens/payload size -- most turns only ever have the main
# window (or main + one editor) open anyway.
MAX_CONTEXT_WINDOWS = 4
# JPEG, not PNG. Found live 2026-09-09 (v0.3.0): Logic's Compressor in its
# brushed-metal Studio VCA skin at 100% view came out ~2.7M base64 chars as a
# 1568px PNG, over server-v3's 2M per-image cap, so every turn 422'd while
# that window was open. The model's vision cost/quality depends on pixel
# dimensions, not bytes -- the same capture at quality 80 is ~340K chars with
# every label/scale number still legible (checked at 1:1). Stay >= 70 to keep
# small scale text crisp.
SCREENSHOT_JPEG_QUALITY = 80
# Mirror of server-v3 api.py's _MAX_SCREENSHOT_CHARS. Anything still over it
# after JPEG encoding is skipped client-side rather than sent to be dropped.
MAX_SCREENSHOT_B64_CHARS = 2 * 1024 * 1024
