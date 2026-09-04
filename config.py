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
# Shared left inset for both the input bar's panel (input_bar.py) and the
# chat bubbles' container (chat_view.py) -- kept as one constant so the two
# independently-scrolling areas stay left-aligned with each other and with
# the bubbles backdrop panel (chat_window.py's paintEvent, which measures the
# input bar's actual panel bounds directly). Previously input-bar-only (added
# there to align with the chat scrollbar); bubbles spilled left past it until
# chat_view.py picked up the same value (found live 2026-09-04, screenshot
# feedback after the backdrop panel was narrowed to the input bar's width).
CONTENT_LEFT_INSET = 70
# Right gutter chat_view.py reserves so the scrollbar sits inboard of the
# backdrop panel's rounded edge (was flush against it). Shared with
# message_widget.py too -- that gutter shrinks the whole scrollable
# container's width, and since user bubbles are right-aligned (assistant
# bubbles are left-aligned, positioned off CONTENT_LEFT_INSET instead and
# unaffected), their own outer margin needs to give back exactly this much
# or they pick up the full gutter on top of their existing margin (found
# live 2026-09-04: user bubbles sat visibly further from the right edge than
# assistant bubbles sat from the left).
CONTENT_RIGHT_INSET = 6

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
