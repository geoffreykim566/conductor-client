"""POST /v3/feedback: a bug report or feedback, with the context dump a bug needs to be fixed."""
import platform

import httpx
from PySide6.QtCore import QThread, Signal

from config import SERVER_BASE_URL, VERSION
from core.ax import state_capture
from core.net.auth import ensure_token, headers
from core.state import identity, recent_context, run_log

try:
    import AppKit
except Exception:  # pragma: no cover - pyobjc missing outside macOS
    AppKit = None

# Logic Pro 10/11 and the Creator Studio Logic Pro (12.x) have different bundle ids.
_LOGIC_BUNDLE_IDS = ("com.apple.mobilelogic", "com.apple.logic10")


def logic_version() -> str | None:
    """'12.4 (com.apple.mobilelogic)' for the first Logic found: a running one first."""
    if AppKit is None:
        return None
    try:
        ws = AppKit.NSWorkspace.sharedWorkspace()
        running = [a.bundleURL() for a in ws.runningApplications()
                   if a.bundleIdentifier() in _LOGIC_BUNDLE_IDS]
        installed = [ws.URLForApplicationWithBundleIdentifier_(b) for b in _LOGIC_BUNDLE_IDS]
        for url in running + installed:
            if url is not None:
                info = AppKit.NSBundle.bundleWithURL_(url).infoDictionary()
                return f"{info['CFBundleShortVersionString']} ({info['CFBundleIdentifier']})"
    except Exception:
        return None
    return None


def versions() -> dict:
    return {
        "conductor": VERSION,
        "logic": logic_version() or "not found",
        "macos": platform.mac_ver()[0] or platform.platform(),
        "chip": platform.machine(),
    }


def build_context(chat: list[dict], server_history: list | None) -> dict:
    """Everything a report carries: the session, recent AX plus a fresh one, the last
    card, the log tail and versions. Takes a fresh AX capture, so call it off the UI thread."""
    try:
        fresh = state_capture.capture_ax_state()
    except Exception:
        fresh = None
    return {
        "chat": chat,
        "server_history": server_history,
        "ax_states": recent_context.ax_states() + [{"label": "at report", "text": fresh}],
        "card": recent_context.last_card(),
        "run_log": run_log.tail(),
        "versions": versions(),
    }


def post_feedback(kind: str, title: str, message: str, context: dict | None) -> None:
    """Raises on failure, so the form can say so and keep what was typed."""
    body = {"kind": kind, "title": title, "message": message,
            "app_version": VERSION, "context": context}
    for attempt in range(2):  # one retry on 401, same rationale as stream_chat
        r = httpx.post(f"{SERVER_BASE_URL}/v3/feedback", headers=headers(ensure_token()),
                       json=body, timeout=30)
        if r.status_code == 401 and attempt == 0:
            identity.clear_token()
            continue
        r.raise_for_status()
        return


class FeedbackWorker(QThread):
    """Builds the context (when asked for) and posts the report off the UI thread."""

    sent = Signal()
    failed = Signal(str)

    def __init__(self, kind: str, title: str, message: str, chat: list[dict] | None,
                 server_history: list | None) -> None:
        super().__init__()
        self._args = (kind, title, message)
        self._chat = chat   # None: send no context
        self._server_history = server_history

    def run(self) -> None:
        try:
            ctx = build_context(self._chat, self._server_history) if self._chat is not None else None
            post_feedback(*self._args, ctx)
        except Exception as e:
            print(f"[feedback] send failed: {e!r}")
            self.failed.emit("Couldn't send. Check your connection and try again.")
            return
        print(f"[feedback] sent kind={self._args[0]} context={self._chat is not None}")
        self.sent.emit()
