"""Global chat history — persists all sessions in a single file."""
import json
from datetime import datetime

from config import APP_SUPPORT_DIR

HISTORY_FILE = APP_SUPPORT_DIR / "history.json"


def new_session_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_sessions() -> list[dict]:
    """Return all sessions as [{id, messages}, ...], oldest first."""
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text())
        return data.get("sessions", [])
    except Exception:
        return []


def clear_all() -> None:
    if HISTORY_FILE.exists():
        HISTORY_FILE.write_text(json.dumps({"sessions": []}, indent=2))


def save_session(session_id: str, messages: list) -> None:
    """Persist one session's messages, creating or updating it."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    sessions = load_sessions()
    serialized = [
        {"role": m.role, "text": m.text, "event_id": m.event_id, "rating": m.rating}
        for m in messages
    ]
    for s in sessions:
        if s["id"] == session_id:
            s["messages"] = serialized
            break
    else:
        sessions.append({"id": session_id, "messages": serialized})
    HISTORY_FILE.write_text(json.dumps({"sessions": sessions}, indent=2))
