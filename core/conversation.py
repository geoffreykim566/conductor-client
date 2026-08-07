"""Conversation state: ordered messages with optional image attachments."""
from dataclasses import dataclass, field
from typing import Literal

# Cap how many messages a single request carries. The server rejects requests
# over 40 messages; we stay well under that with margin (~15 turns). This also
# keeps input-token cost flat on long chats — older text turns stop being
# re-sent once the window fills. Not a model-context limit; a self-imposed cap.
_MAX_CONTEXT_MESSAGES = 30


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

    def to_api_format(
        self,
        keep_only_last_image: bool = True,
        max_messages: int = _MAX_CONTEXT_MESSAGES,
    ) -> list[dict]:
        """Convert to the message list format expected by Anthropic's API.

        By default, images are kept only on the most recent user message. A
        fresh screenshot is captured every turn, so older turns' screenshots are
        stale and re-sending them costs ~1.5k image tokens each, every request —
        a quadratic cost as the conversation grows. Dropping them keeps image
        cost constant (one screenshot per request).

        The list is also capped at `max_messages` to stay under the server's
        per-request ceiling: we keep the most recent messages and drop any
        leading assistant turn so the trimmed list still starts on a user
        message (the API requires that). The latest user turn and its screenshot
        are near the end, so they always survive the trim.
        """
        last_user_idx = max(
            (i for i, m in enumerate(self._messages) if m.role == "user"),
            default=-1,
        )
        out: list[dict] = []
        for i, msg in enumerate(self._messages):
            keep_imgs = msg.images_b64 and (not keep_only_last_image or i == last_user_idx)
            if msg.role == "user" and keep_imgs:
                content: list[dict] = []
                for b64 in msg.images_b64:
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64,
                        },
                    })
                content.append({"type": "text", "text": msg.text})
                out.append({"role": msg.role, "content": content})
            else:
                out.append({"role": msg.role, "content": msg.text})

        if len(out) > max_messages:
            out = out[-max_messages:]
            while out and out[0]["role"] != "user":
                out.pop(0)
        return out

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
