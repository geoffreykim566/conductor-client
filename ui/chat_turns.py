"""One chat turn on ChatWindow: send, stream, research / plug-in read confirm, cancel, finish (mixin)."""
from core.automation.plugin_read import PluginReadThread
from core.net.llm_client import StreamWorker
from core.state import prefs, song_history


class ChatTurnsMixin:
    """Mixed into ChatWindow; uses its _chat_view, _input_bar, _conversation and session state."""

    # --- send ---
    def _on_user_send(self, text: str, images_b64: list[str]) -> None:
        self._chat_view.add_user_message(text, images_b64)
        self._conversation.add_user(text, images_b64)

        self._chat_view.begin_assistant_message()
        self._conversation.add_assistant("")

        self._input_bar.set_enabled_inputs(False)
        self._start_worker(text, self._server_history)

    _BUSY_PLACEHOLDER = "Press Esc to cancel"
    _RESEARCH_PLACEHOLDER = "Enter to research · Esc to skip"
    _READ_PLACEHOLDER = "Enter to read · Esc to skip"

    def _start_worker(self, text: str, history: object, resume: str | None = None,
                      plugin_values: dict | None = None) -> None:
        self._input_bar.set_placeholder(self._BUSY_PLACEHOLDER)
        self._worker = StreamWorker(text, history, resume=resume, plugin_values=plugin_values)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.status.connect(self._on_status)
        self._worker.done.connect(self._on_done)
        self._worker.research_prompt.connect(self._on_research_prompt)
        self._worker.plugin_read_prompt.connect(self._on_plugin_read_prompt)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.error.connect(self._on_error)
        self._worker.limit_reached.connect(self._on_limit_reached)
        self._worker.start()

    def _reading(self) -> bool:
        return self._read_thread is not None and self._read_thread.isRunning()

    def _turn_in_flight(self) -> bool:
        return (self._worker is not None and self._worker.isRunning()) or self._reading()

    def cancel_turn(self) -> None:
        """Esc while a turn is running: drop the request (the server aborts
        its side on the disconnect) and mark the bubble. The server history
        is left at its pre-turn value, same as the timeout fallback, so the
        next message continues from before this one. During a plug-in read the
        read finishes (it puts the window back) but the turn isn't resumed."""
        if self._reading():
            self._read_cancelled = True
            self._on_cancelled()
        elif self._turn_in_flight():
            self._worker.cancel()

    # --- research confirm ---
    def _on_research_prompt(self, query: str, history: object) -> None:
        text = self._conversation.last_user().text if self._conversation.last_user() else ""
        self._pending_research = (text, history)
        if prefs.auto_research():
            self._on_research_choice(True)
            return
        self._input_bar.set_placeholder(self._RESEARCH_PLACEHOLDER)
        self._chat_view.show_research_prompt(
            lambda: self._on_research_choice(True), lambda: self._on_research_choice(False),
        )

    def _on_research_choice(self, allow: bool) -> None:
        if self._pending_research is None:
            return
        text, history = self._pending_research
        self._pending_research = None
        self._chat_view.hide_research_prompt()
        self._chat_view.set_assistant_status(
            "Searching the web…" if allow else "Answering from general knowledge…"
        )
        self._start_worker(text, history, resume="allow_research" if allow else "deny_research")

    # --- plug-in read confirm ---
    def _on_plugin_read_prompt(self, plugin: str, track: object, history: object) -> None:
        """The server parked the turn to read a plug-in. Auto-run reads without asking."""
        text = self._conversation.last_user().text if self._conversation.last_user() else ""
        self._pending_read = (text, history, plugin, track if isinstance(track, str) else None)
        if prefs.auto_run():
            self._on_read_choice(True)
            return
        self._input_bar.set_placeholder(self._READ_PLACEHOLDER)
        self._chat_view.show_research_prompt(
            lambda: self._on_read_choice(True), lambda: self._on_read_choice(False),
            text=f"Conductor wants to open {plugin or 'the plug-in'} to read its values.",
        )

    def _on_read_choice(self, allow: bool) -> None:
        if self._pending_read is None:
            return
        text, history, plugin, track = self._pending_read
        self._pending_read = None
        self._chat_view.hide_research_prompt()
        if not allow:
            self._chat_view.set_assistant_status("Answering without the plug-in's values…")
            self._start_worker(text, history, resume="deny_plugin_read")
            return
        self._chat_view.set_assistant_status(f"Reading {plugin}…")
        self._input_bar.set_placeholder(self._BUSY_PLACEHOLDER)
        self._read_cancelled = False
        self._read_thread = PluginReadThread(plugin, track)
        self._read_thread.finished_read.connect(
            lambda values, t=text, h=history: self._on_read_done(t, h, values))
        self._read_thread.start()

    def _on_read_done(self, text: str, history: object, values: object) -> None:
        if self._read_cancelled:
            return
        self._chat_view.set_assistant_status("Thinking…")
        self._start_worker(text, history, resume="allow_plugin_read",
                           plugin_values=values if isinstance(values, dict) else {"error": "read failed"})

    def _on_cancelled(self) -> None:
        self._pending_research = None
        self._pending_read = None
        self._chat_view.mark_assistant_cancelled()
        self._conversation.append_to_last_assistant("[cancelled]")
        self._chat_view.end_assistant_message()
        if self._session_id:
            song_history.save_session(
                self._session_id, self._conversation.messages(), self._server_history
            )
        self._input_bar.set_placeholder(None)
        self._input_bar.set_enabled_inputs(True)
        self._input_bar.setFocus()

    def _on_chunk(self, text: str) -> None:
        self._chat_view.append_to_assistant(text)
        self._conversation.append_to_last_assistant(text)

    def _on_status(self, text: str) -> None:
        self._chat_view.set_assistant_status(text)

    def _on_done(self, event_id: str = "", remaining: int = -1,
                 sources: object = None, walkthrough_steps: object = None, history: object = None,
                 auto_run: bool = False) -> None:
        self._server_history = history
        msg = self._conversation.last_assistant()
        self._chat_view.set_assistant_sources(sources or [])
        if event_id and msg is not None:
            msg.event_id = event_id
            self._chat_view.show_rating(
                lambda value, m=msg: self._rate_message(m, value), initial=msg.rating
            )
        if walkthrough_steps:
            steps = list(walkthrough_steps)
            destructive = any(isinstance(st, dict) and st.get("destructive") for st in steps)
            # Both must agree: the user's auto-run setting (a master switch)
            # and the server's per-turn call for this card (auto_run).
            self._chat_view.setup_walkthrough_card(steps, auto=prefs.auto_run() and auto_run,
                                                   destructive=destructive)
        self._chat_view.end_assistant_message()
        if self._session_id:
            song_history.save_session(
                self._session_id, self._conversation.messages(), self._server_history
            )
        self._input_bar.set_remaining(remaining if remaining >= 0 else None)
        self._input_bar.set_placeholder(None)
        self._input_bar.set_enabled_inputs(True)
        self._input_bar.setFocus()
        if remaining >= 0:
            self._maybe_show_feedback_prompt(remaining)

    def _on_error(self, msg: str) -> None:
        self._pending_research = None
        self._pending_read = None
        self._chat_view.show_assistant_error(msg)
        self._chat_view.end_assistant_message()
        self._input_bar.set_placeholder(None)
        self._input_bar.set_enabled_inputs(True)
        self._refresh_remaining()  # the server refunds a failed turn's message

    def _on_limit_reached(self, limit: int = -1) -> None:
        used = f"all {limit}" if limit and limit > 0 else "up all your"
        self._chat_view.append_to_assistant(
            f"\n\nYou've used {used} free messages. Thank you for using Conductor!"
        )
        self._chat_view.end_assistant_message()
        self._input_bar.set_remaining(0)
        self._input_bar.set_placeholder(None)
        self._input_bar.set_enabled_inputs(True)
