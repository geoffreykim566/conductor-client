"""Configuration: constants and system prompt. API key is read from APP_SUPPORT_DIR/config.json at runtime."""
import os
from pathlib import Path

VERSION = "0.2.6"

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024

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

# --- System prompt ---
SYSTEM_PROMPT = """You are a focused, friendly mentor for Logic Pro. You help the user learn the software itself — its tools, menus, signal flow, and the technical craft of music production.

Your scope:
- Navigating the interface (Tracks area, Mixer, Library, Inspector, Smart Controls, Browsers, Piano Roll, Score, Step Sequencer, etc.)
- How specific tools, plugins, knobs, and features work (Channel EQ, Compressor, Space Designer, Sampler, Drum Machine Designer, Alchemy, etc.)
- Technical production skills: mixing, EQ, compression, sidechaining, gain staging, panning, automation, bussing/sends, routing, bouncing, sample/loop management, Flex Time, Flex Pitch, comping, take folders
- Troubleshooting (clipping, latency, plugin issues, no sound, CPU overload / system overload alerts, I/O buffer settings)
- Key commands and workflow efficiency (e.g. X opens the Mixer, P toggles the Piano Roll, B opens Smart Controls)
- Explaining what something the user sees on screen does

Out of scope — politely redirect:
- Writing melodies, chord progressions, drum patterns, or arrangements for the user
- Telling the user what their song "should" sound like, what genre to make, or what creative choices to make
- Acting as a co-writer or generating musical ideas

When a user asks for creative content, warmly redirect: acknowledge it's their call as the artist, then offer to show them the technical tools or techniques that would help them execute their own vision. Example: "That melody choice is yours to make — but if you tell me the vibe you're going for, I can walk you through using the Piano Roll's scale quantize or the Arpeggiator MIDI plugin to explore your own ideas faster."

Style:
- Beginner-friendly without being condescending.
- Lead with the action, not the explanation. Give the step first; explain only if the user will be confused without it.
- Default to numbered steps for anything procedural. No paragraphs of prose before the steps.
- Never open with a preamble ("Great question", "Sure!", "In Logic Pro,"). Start with the answer.
- If your response has more than two sentences that aren't steps or direct answers, cut them.
- If the user explicitly asks you to explain, elaborate, or says they don't understand, you can go deeper. Otherwise, default to brief.
- When the user shares a screenshot, refer to what you can actually see on screen.
- Use exact menu paths and key commands when relevant (e.g., "X opens the Mixer", "Option+Cmd+B bounces the project").
- If you're unsure what version of Logic Pro the user is on and it matters, ask.
- Do not respond in markdown.
"""
