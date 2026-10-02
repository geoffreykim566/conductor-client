"""Main floating chat window. Frameless, always-on-top, minimizes to a small bubble.

A permanent, slightly-transparent rounded panel (see paintEvent) sits behind
the message bubbles -- Logic Pro showing through blank space behind the
bubbles read as chaotic given that space was never clickable anyway. Stops
above the input bar, which already draws its own backing panel (#inputPanel,
ui/style.py). History is a page in the same QStackedWidget as the chat view,
swapped in over the bubbles panel (see _show_history/_show_chat) rather than
a separate popup window -- Settings and its confirm dialogs still use
ui/popup.py's Popup for that.
"""
from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config import FEEDBACK_PROMPT_REMAINING_THRESHOLDS
from core.net.account import post_rating_async
from core.net.llm_client import MeWorker, StreamWorker
from core.net.update_checker import UpdateChecker
from core.state import prefs, song_history
from core.state.conversation import Conversation
from core.state.prefs import (
    clear_window_pos,
    clear_window_size,
    get_saved_window_pos,
    get_saved_window_size,
    is_feedback_never_show,
    reset_feedback_for_new_version,
    save_window_pos,
    save_window_size,
)
from ui.chat_view import ChatView
from ui.input_bar import InputBar
from ui.session_list import SessionListPanel
from ui.onboarding.feedback_dialog import FeedbackDialog
from ui.onboarding.update_popup import UpdatePopup
from ui.settings_panel import SettingsPanel
from ui.theme import (
    MAX_WINDOW_HEIGHT,
    MAX_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    MINIMIZED_SIZE,
    PANEL,
    PANEL_ALPHA,
    PANEL_BORDER,
    PANEL_BORDER_ALPHA,
    PANEL_RADIUS,
    WINDOW_HEIGHT,
    WINDOW_MARGIN,
    WINDOW_WIDTH,
    qcolor,
)

_GEOMETRY_SAVE_DELAY_MS = 300

_PAGE_CHAT = 0
_PAGE_HISTORY = 1


class _MinimizedBubble(QWidget):
    """Tiny floating circle shown when the main window is minimized."""

    def __init__(self, parent_window: "ChatWindow") -> None:
        super().__init__()
        self._parent_window = parent_window
        self._drag_offset: QPoint | None = None
        self._press_pos: QPoint | None = None
        self._dragging = False

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(MINIMIZED_SIZE, MINIMIZED_SIZE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._btn = QPushButton("🎹")
        self._btn.setObjectName("bubble")
        self._btn.setFixedSize(MINIMIZED_SIZE, MINIMIZED_SIZE)
        self._btn.clicked.connect(parent_window.restore_from_bubble)
        self._btn.installEventFilter(self)
        layout.addWidget(self._btn)

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        if obj is self._btn:
            t = event.type()
            if t == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
                self._press_pos = event.globalPosition().toPoint()
                self._drag_offset = self._press_pos - self.pos()
                self._dragging = False
            elif t == QEvent.Type.MouseMove and self._drag_offset is not None:
                if not self._dragging and (
                    event.globalPosition().toPoint() - self._press_pos
                ).manhattanLength() >= 5:
                    self._dragging = True
                    self._btn.setDown(False)
                if self._dragging:
                    self.move(event.globalPosition().toPoint() - self._drag_offset)
            elif t == QEvent.Type.MouseButtonRelease:
                self._drag_offset = None
                self._press_pos = None
                self._dragging = False
        return super().eventFilter(obj, event)


class ChatWindow(QWidget):
    """Main floating chat window."""

    def __init__(self) -> None:
        super().__init__()
        reset_feedback_for_new_version()
        self.setObjectName("chatWindow")
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        # Once an app-wide stylesheet exists, Qt's style engine paints a
        # default opaque fill for any widget it doesn't have a specific rule
        # for (previously masked by the old fully-opaque `_root` panel
        # covering the whole window) — this window itself has no rule, so it
        # needs styled-background painting turned off explicitly to stay
        # see-through. Children keep it on so their own bubble/bar rules
        # from ui/style.py still render. The permanent backdrop panel (see
        # paintEvent) is drawn directly instead of via a QSS rule on this
        # widget -- a toggled QSS rule here didn't reliably repaint
        # (translucent frameless top-level + zero-margin children covering the
        # edge), direct QPainter drawing behind the children is more robust.
        self.setAttribute(Qt.WA_StyledBackground, False)
        # Guards resizeEvent/moveEvent below from persisting geometry during
        # this constructor's own initial resize()/move() calls — without it,
        # the very first launch immediately saves whatever size was just set
        # (default or restored) as "saved", permanently shadowing any future
        # default-size change in theme.py from then on.
        self._geometry_ready = False
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.setMaximumSize(MAX_WINDOW_WIDTH, MAX_WINDOW_HEIGHT)
        saved_size = get_saved_window_size()
        self.resize(*(saved_size or (WINDOW_WIDTH, WINDOW_HEIGHT)))

        self._conversation = Conversation()
        # Opaque server-returned turn history for the current session — round-
        # tripped verbatim to /v3/chat each turn so the server can keep real
        # multi-turn continuity without pinning any state of its own. None
        # starts a fresh conversation server-side.
        self._server_history: list[dict] | None = None
        self._worker: StreamWorker | None = None
        self._me_worker: MeWorker | None = None
        # Set while the assistant bubble is asking "research the web?":
        # (original message text, parked history). Enter/Esc route here
        # first (see eventFilter) instead of cancelling.
        self._pending_research: tuple[str, object] | None = None
        self._session_id: str | None = None
        self._settings_popup: SettingsPanel | None = None
        self._update_popup: UpdatePopup | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # No uniform spacing -- the controls-to-chat_view gap is controlled
        # entirely by controls_row's own bottom margin instead (input_bar.py),
        # so it's one clean lever instead of margin+spacing stacking
        # unpredictably (found live 2026-09-04: with 8px shared spacing here,
        # matching controls_row's top/bottom margins still left the bottom gap
        # visibly bigger, since spacing added onto it but not the top side).
        # chat_view-to-input_bar keeps its own explicit gap below instead.
        layout.setSpacing(0)

        # Built before being placed so its .controls widget (new-chat/history/
        # minimize/close) exists to add above the bubbles, ahead of the bubbles
        # panel itself below -- moved there from the top of the input bar's own
        # panel 2026-09-04 (user preference), sitting directly on the bubbles
        # backdrop panel (paintEvent) instead of inside a nested one.
        self._input_bar = InputBar()
        self._input_bar.send.connect(self._on_user_send)
        self._input_bar.enter_empty.connect(self._on_enter_empty)
        self._input_bar.new_chat_requested.connect(self._on_new_chat)
        self._input_bar.history_requested.connect(self._on_toggle_history)
        self._input_bar.minimize_requested.connect(self.minimize_to_bubble)
        self._input_bar.close_requested.connect(self.hide_to_dock)
        layout.addWidget(self._input_bar.controls)

        self._chat_view = ChatView()
        self._session_panel = SessionListPanel()
        self._session_panel.session_selected.connect(self._on_session_selected)
        self._session_panel.closed.connect(self._show_chat)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._chat_view)      # _PAGE_CHAT
        self._stack.addWidget(self._session_panel)  # _PAGE_HISTORY
        layout.addWidget(self._stack, 1)

        layout.addSpacing(8)
        layout.addWidget(self._input_bar)

        self._geometry_save_timer = QTimer(self)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.timeout.connect(self.persist_geometry)

        QApplication.instance().installEventFilter(self)

        self._feedback_dialog: FeedbackDialog | None = None
        self._bubble: _MinimizedBubble | None = None
        saved_pos = get_saved_window_pos()
        if saved_pos and QGuiApplication.screenAt(QPoint(saved_pos[0], saved_pos[1])):
            self.move(saved_pos[0], saved_pos[1])
        else:
            self._anchor_to_bottom_right()
        self._geometry_ready = True
        self._load_latest_session()
        self._refresh_remaining()
        self._update_checker = None
        self._start_update_check()
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(6 * 60 * 60 * 1000)  # every 6 hours
        self._update_timer.timeout.connect(self._start_update_check)
        self._update_timer.start()

    # --- geometry ---
    def resizeEvent(self, event) -> None:
        if self._geometry_ready:
            self._geometry_save_timer.start(_GEOMETRY_SAVE_DELAY_MS)
        super().resizeEvent(event)

    def moveEvent(self, event) -> None:
        if self._geometry_ready:
            self._geometry_save_timer.start(_GEOMETRY_SAVE_DELAY_MS)
        super().moveEvent(event)

    def persist_geometry(self) -> None:
        save_window_size(self.width(), self.height())
        save_window_pos(self.x(), self.y())

    def _on_reset_size(self) -> None:
        clear_window_size()
        # A plain resize() keeps the top-left corner fixed and grows/shrinks
        # toward bottom-right -- wrong anchor here, since the window normally
        # lives pinned near the screen's bottom-right (_anchor_to_bottom_right)
        # and that corner is the one that should stay put.
        right, bottom = self.x() + self.width(), self.y() + self.height()
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.move(right - WINDOW_WIDTH, bottom - WINDOW_HEIGHT)

    def _on_reset_position(self) -> None:
        clear_window_pos()
        self._anchor_to_bottom_right()

    # --- painting ---
    def paintEvent(self, event) -> None:
        # Same look as #inputPanel (ui/style.py) -- drawn directly rather than
        # via a stylesheet rule, see the WA_StyledBackground comment in
        # __init__. Permanent since 2026-09-04 -- with no backdrop at all,
        # Logic Pro's own UI showed through every blank area behind the
        # floating bubbles, which read as chaotic.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(qcolor(PANEL_BORDER, PANEL_BORDER_ALPHA))
        painter.setBrush(qcolor(PANEL, PANEL_ALPHA))
        # Spans the full window width -- the window IS the panel, nothing is
        # laid out past its edges. Stops a few px above the input bar, which
        # draws its own pill, so the two rounded shapes read as separate.
        panel_rect = QRect(0, 0, self.width(), self._input_bar.y() - 4)
        painter.drawRoundedRect(
            panel_rect.adjusted(0, 0, -1, -1), PANEL_RADIUS, PANEL_RADIUS
        )
        super().paintEvent(event)

    # --- positioning ---
    def _anchor_to_bottom_right(self) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            screen.right() - self.width() - WINDOW_MARGIN,
            screen.bottom() - self.height() - WINDOW_MARGIN,
        )

    # --- minimize / restore / dock ---
    def minimize_to_bubble(self) -> None:
        if self._bubble is None:
            self._bubble = _MinimizedBubble(self)
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self._bubble.move(
            screen.right() - MINIMIZED_SIZE - WINDOW_MARGIN,
            screen.bottom() - MINIMIZED_SIZE - WINDOW_MARGIN,
        )
        self._bubble.show()
        self.hide()

    def restore_from_bubble(self) -> None:
        if self._bubble is not None:
            self._bubble.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    def open_from_dock(self) -> None:
        if self._bubble is not None:
            self._bubble.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_to_dock(self) -> None:
        if self._bubble is not None:
            self._bubble.hide()
        self.hide()

    # --- history page ---
    def _show_chat(self) -> None:
        self._stack.setCurrentIndex(_PAGE_CHAT)

    def _show_history(self) -> None:
        self._session_panel.load(song_history.load_sessions(), self._session_id)
        self._stack.setCurrentIndex(_PAGE_HISTORY)

    def _on_toggle_history(self) -> None:
        if self._stack.currentIndex() == _PAGE_HISTORY:
            self._show_chat()
        else:
            self._show_history()

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

    # --- settings popup (opened from the macOS menu bar) ---
    def open_settings(self) -> None:
        if self._settings_popup is not None and self._settings_popup.isVisible():
            self._settings_popup.raise_()
            self._settings_popup.activateWindow()
            return
        self._settings_popup = SettingsPanel()
        self._settings_popup.history_cleared.connect(self._on_history_cleared)
        self._settings_popup.reset_size_requested.connect(self._on_reset_size)
        self._settings_popup.reset_position_requested.connect(self._on_reset_position)
        self._settings_popup.center_on_screen()
        self._settings_popup.show()

    # --- remaining-messages counter ---
    def _refresh_remaining(self) -> None:
        """Fetch the user's free-tier usage in the background and update the input bar."""
        self._me_worker = MeWorker()
        self._me_worker.loaded.connect(self._input_bar.set_remaining)
        self._me_worker.start()

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

    def _start_worker(self, text: str, history: object, resume: str | None = None) -> None:
        self._input_bar.set_placeholder(self._BUSY_PLACEHOLDER)
        self._worker = StreamWorker(text, history, resume=resume)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.status.connect(self._on_status)
        self._worker.done.connect(self._on_done)
        self._worker.research_prompt.connect(self._on_research_prompt)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.error.connect(self._on_error)
        self._worker.limit_reached.connect(self._on_limit_reached)
        self._worker.start()

    def _turn_in_flight(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def cancel_turn(self) -> None:
        """Esc while a turn is running: drop the request (the server aborts
        its side on the disconnect) and mark the bubble. The server history
        is left at its pre-turn value, same as the timeout fallback, so the
        next message continues from before this one."""
        if self._turn_in_flight():
            self._worker.cancel()

    # --- research confirm (2026-09-13) ---
    def _on_research_prompt(self, query: str, history: object) -> None:
        text = self._conversation.last_user().text if self._conversation.last_user() else ""
        self._pending_research = (text, history)
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

    def _on_cancelled(self) -> None:
        self._pending_research = None
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
                 source_tier: str = "", sources: object = None,
                 walkthrough_steps: object = None, history: object = None,
                 auto_run: bool = False) -> None:
        self._server_history = history
        msg = self._conversation.last_assistant()
        self._chat_view.set_assistant_tier(source_tier, sources or [])
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

    # --- feedback prompt ---
    def _maybe_show_feedback_prompt(self, remaining: int) -> None:
        if is_feedback_never_show():
            return
        if remaining in FEEDBACK_PROMPT_REMAINING_THRESHOLDS:
            self._feedback_dialog = FeedbackDialog()
            self._feedback_dialog.closed.connect(self._on_feedback_dialog_closed)
            self._feedback_dialog.show()

    def _on_feedback_dialog_closed(self) -> None:
        self._feedback_dialog = None

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

    # --- update check ---
    def _start_update_check(self) -> None:
        self._update_checker = UpdateChecker()
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.start()

    def _on_update_available(self, version: str) -> None:
        if self._update_popup is not None and self._update_popup.isVisible():
            return
        self._update_popup = UpdatePopup(version)
        self._update_popup.get_clicked.connect(self._on_update_get)
        self._update_popup.show()

    def _on_update_get(self) -> None:
        from config import WEBSITE_URL
        QDesktopServices.openUrl(QUrl(WEBSITE_URL))
        if self._update_popup is not None:
            self._update_popup.close()

    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return False
        key = event.key()
        # Research prompt showing: Enter = Yes, Esc = No. Checked before the
        # cancel path below so Esc skips research rather than killing the
        # turn; a second Esc (during the resumed answer) then cancels.
        if self._pending_research is not None:
            if key in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
                self._on_research_choice(True)
                return True
            if key == Qt.Key_Escape:
                self._on_research_choice(False)
                return True
        if key == Qt.Key_Escape and self._turn_in_flight():
            self.cancel_turn()
            return True
        if (key in (Qt.Key_Return, Qt.Key_Enter)
                and not (event.modifiers() & Qt.ShiftModifier)
                and self._chat_view.has_active_walkthrough()
                and not self._input_bar._text.toPlainText().strip()):
            self._chat_view.wt_enter()
            return True
        return False

    def _on_enter_empty(self) -> None:
        self._chat_view.wt_enter()

    def prepare_for_quit(self) -> None:
        """Called from the app's aboutToQuit — stop any active walkthrough
        thread before QApplication teardown destroys it while still running
        (Qt6 aborts the process in that case)."""
        self._chat_view.force_end_active_walkthrough()

    def _on_error(self, msg: str) -> None:
        msg_lower = msg.lower()
        if any(word in msg_lower for word in ("401", "unauthorized", "authentication", "invalid x-api-key", "invalid api")):
            display = "Invalid API key. Open Conductor's menu bar → Settings to reset it."
        else:
            display = msg
        self._pending_research = None
        self._chat_view.append_to_assistant(f"\n\n[error] {display}")
        self._chat_view.end_assistant_message()
        self._input_bar.set_placeholder(None)
        self._input_bar.set_enabled_inputs(True)

    def _on_limit_reached(self, limit: int = -1) -> None:
        used = f"all {limit}" if limit and limit > 0 else "up all your"
        self._chat_view.append_to_assistant(
            f"\n\nYou've used {used} free messages. Thank you for using Conductor!"
        )
        self._chat_view.end_assistant_message()
        self._input_bar.set_remaining(0)
        self._input_bar.set_placeholder(None)
        self._input_bar.set_enabled_inputs(True)
