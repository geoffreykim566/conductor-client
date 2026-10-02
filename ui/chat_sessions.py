"""Chat sessions on ChatWindow: load, switch, start new, clear, persist ratings (mixin)."""
from core.net.account import post_rating_async
from core.state import song_history


class ChatSessionsMixin:
    """Mixed into ChatWindow; owns _session_id / _server_history / _conversation bookkeeping."""

    def _load_latest_session(self) -> None:
        """Load the most recent session, or start empty."""
        sessions = song_history.load_sessions()
        if sessions:
            latest = sessions[-1]
            self._session_id = latest["id"]
            self._server_history = latest.get("server_history")
            self._conversation.clear()
            self._conversation.load_messages(latest["messages"])
            self._chat_view.load_history(
                self._conversation.messages(), self._rate_message
            )
        else:
            self._session_id = song_history.new_session_id()
            self._server_history = None
            self._conversation.clear()
            self._chat_view.clear()

    # --- new chat ---
    def _on_new_chat(self) -> None:
        if self._session_id and self._conversation.messages():
            song_history.save_session(
                self._session_id, self._conversation.messages(), self._server_history
            )
        self._session_id = song_history.new_session_id()
        self._server_history = None
        self._conversation.clear()
        self._chat_view.clear()
        self._show_chat()

    def _on_session_selected(self, session_id: str) -> None:
        if self._session_id and self._conversation.messages():
            song_history.save_session(
                self._session_id, self._conversation.messages(), self._server_history
            )
        sessions = song_history.load_sessions()
        for s in sessions:
            if s["id"] == session_id:
                self._session_id = session_id
                self._server_history = s.get("server_history")
                self._conversation.clear()
                self._conversation.load_messages(s["messages"])
                self._chat_view.load_history(
                    self._conversation.messages(), self._rate_message
                )
                break
        self._show_chat()

    def _rate_message(self, message, value: int) -> None:
        """Persist a thumbs vote (or undo, value=0) and report it to the server."""
        if message.event_id:
            post_rating_async(message.event_id, value)
        message.rating = value
        if self._session_id:
            song_history.save_session(
                self._session_id, self._conversation.messages(), self._server_history
            )

    def _on_history_cleared(self) -> None:
        self._session_id = song_history.new_session_id()
        self._server_history = None
        self._conversation.clear()
        self._chat_view.clear()
