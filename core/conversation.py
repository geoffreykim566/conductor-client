"""Conversation state: ordered messages with optional image attachments.

Display-only — what actually gets sent to the server each turn is the new
user text plus the opaque `history` blob the server's last response
returned (see ChatWindow._server_history), not anything built from this
class. This class exists purely to drive the chat bubbles UI and local
session persistence.
"""
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Message:
    role: Literal["user", "assistant"]
    text: str
    # Base64-encoded PNG images attached to this message (user messages only).
    images_b64: list[str] = field(default_factory=list)
    # Server event id for assistant messages, so the bubble stays rateable even
    # after reload. None until the response finishes (or for user messages).
    event_id: str | None = None
    # Thumbs state: 0 = no vote, 1 = up, -1 = down.
    rating: int = 0


class Conversation:
    """In-memory ordered list of messages, formatted for the Anthropic API."""

    def __init__(self) -> None:
        self._messages: list[Message] = []

    def add_user(self, text: str, images_b64: list[str] | None = None) -> Message:
        msg = Message(role="user", text=text, images_b64=list(images_b64 or []))
        self._messages.append(msg)
        return msg

    def add_assistant(self, text: str = "") -> Message:
        msg = Message(role="assistant", text=text)
        self._messages.append(msg)
        return msg

    def append_to_last_assistant(self, chunk: str) -> None:
        """Append streamed text to the most recent assistant message."""
        self._messages[-1].text += chunk

    def last_assistant(self) -> Message | None:
        """The most recent assistant message, or None."""
        for msg in reversed(self._messages):
            if msg.role == "assistant":
                return msg
        return None

    def last_user(self) -> Message | None:
        """The most recent user message, or None."""
        for msg in reversed(self._messages):
            if msg.role == "user":
                return msg
        return None

    def messages(self) -> list[Message]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    def load_messages(self, saved: list[dict]) -> None:
        """Restore text-only messages from saved history (no images)."""
        self._messages = [
            Message(
                role=m["role"],
                text=m["text"],
                event_id=m.get("event_id"),
                rating=m.get("rating", 0),
            )
            for m in saved
        ]
