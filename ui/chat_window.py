"""Main floating chat window. Frameless, always-on-top, minimizes to a small bubble.

No outer window panel/backdrop — only the input bar and message bubbles are
boxed; everything floats directly over Logic Pro. Settings and history are
separate popup windows (see ui/popup.py), not stack pages.
"""
from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from config import (
    FEEDBACK_PROMPT_REMAINING_THRESHOLDS,
    MAX_WINDOW_HEIGHT,
    MAX_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    MINIMIZED_SIZE,
    WINDOW_HEIGHT,
    WINDOW_MARGIN,
    WINDOW_WIDTH,
)
from core.conversation import Conversation
from core.llm_client import MeWorker, StreamWorker
from core import song_history
from core.server_client import post_rating_async
from ui.chat_view import ChatView
from ui.input_bar import InputBar
from ui.popup import Popup
from ui.session_list import SessionListPanel
from ui.setup_screen import (
    FeedbackDialog,
    clear_window_pos,
    clear_window_size,
    get_saved_window_pos,
    get_saved_window_size,
    is_feedback_never_show,
    reset_feedback_for_new_version,
    save_window_pos,
    save_window_size,
)
from ui.settings_panel import SettingsPanel

_GEOMETRY_SAVE_DELAY_MS = 300
_TOP_ROOM = 44  # reserved band at the window's top for floating controls


class _UpdatePopup(Popup):
    """Shown at launch when a newer version is available. Reappears every
    launch while an update is available — Skip only dismisses this session,
    it doesn't persist a permanent opt-out."""

    get_clicked = Signal()

    def __init__(self, version: str) -> None:
        super().__init__("UPDATE AVAILABLE", width=300)
        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        lbl = QLabel(f"Conductor v{version} is available.")
        lbl.setObjectName("stepLabel")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        row = QHBoxLayout()
        get_btn = QPushButton("Download")
        get_btn.setObjectName("primary")
        get_btn.clicked.connect(self.get_clicked)
        row.addWidget(get_btn)
        skip_btn = QPushButton("Skip")
        skip_btn.setObjectName("secondary")
        skip_btn.clicked.connect(self.close)
        row.addWidget(skip_btn)
        layout.addLayout(row)


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
        # from ui/style.py still render.
        self.setAttribute(Qt.WA_StyledBackground, False)
        # Guards resizeEvent/moveEvent below from persisting geometry during
        # this constructor's own initial resize()/move() calls — without it,
        # the very first launch immediately saves whatever size was just set
        # (default or restored) as "saved", permanently shadowing any future
        # default-size change in config.py from then on.
        self._geometry_ready = False
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.setMaximumSize(MAX_WINDOW_WIDTH, MAX_WINDOW_HEIGHT)
        saved_size = get_saved_window_size()
        self.resize(*(saved_size or (WINDOW_WIDTH, WINDOW_HEIGHT)))

        self._conversation = Conversation()
        self._worker: StreamWorker | None = None
        self._me_worker: MeWorker | None = None
        self._session_id: str | None = None
        self._session_popup: SessionListPanel | None = None
        self._settings_popup: SettingsPanel | None = None
        self._update_popup: _UpdatePopup | None = None

        layout = QVBoxLayout(self)
        # Real reserved space at the top (not just a fade) — the floating
        # minimize/close/message-count controls live in this band, clear of
        # where chat bubbles start, instead of overlapping scrolled content.
        layout.setContentsMargins(0, _TOP_ROOM, 0, 0)
        layout.setSpacing(0)

        self._chat_view = ChatView()
        layout.addWidget(self._chat_view, 1)

        self._input_bar = InputBar()
        self._input_bar.send.connect(self._on_user_send)
        self._input_bar.enter_empty.connect(self._on_enter_empty)
        self._input_bar.new_chat_requested.connect(self._on_new_chat)
        self._input_bar.history_requested.connect(self._on_toggle_history)
        layout.addWidget(self._input_bar)

        # Floating top-left message count — no backdrop, just text.
        self._msg_count_label = QLabel("", self)
        self._msg_count_label.setObjectName("remainingLabel")

        # Floating top-right controls: no backdrop, just icons.
        self._min_btn = QPushButton("—", self)
        self._min_btn.setObjectName("headerBtn")
        self._min_btn.setFixedSize(20, 20)
        self._min_btn.clicked.connect(self.minimize_to_bubble)

        self._close_btn = QPushButton("✕", self)
        self._close_btn.setObjectName("headerBtn")
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.clicked.connect(QApplication.instance().quit)

        self._grip = QSizeGrip(self)
        self._grip.setFixedSize(16, 16)
        self._grip.setStyleSheet("QSizeGrip { background: transparent; }")

        self._position_floating_controls()

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
    def _position_floating_controls(self) -> None:
        w, h = self.width(), self.height()
        btn_y = (_TOP_ROOM - self._close_btn.height()) // 2
        self._close_btn.move(w - 8 - self._close_btn.width(), btn_y)
        self._min_btn.move(
            w - 8 - self._close_btn.width() - 4 - self._min_btn.width(), btn_y
        )
        self._msg_count_label.move(8, (_TOP_ROOM - self._msg_count_label.height()) // 2)
        self._grip.move(w - self._grip.width(), h - self._grip.height())
        self._msg_count_label.raise_()
        self._min_btn.raise_()
        self._close_btn.raise_()
        self._grip.raise_()

    def resizeEvent(self, event) -> None:
        self._position_floating_controls()
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

    def _on_reset_window(self) -> None:
        clear_window_size()
        clear_window_pos()
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._anchor_to_bottom_right()

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

    # --- history popup ---
    def _on_toggle_history(self) -> None:
        if self._session_popup is not None and self._session_popup.isVisible():
            self._session_popup.close()
            return
        self._session_popup = SessionListPanel()
        self._session_popup.session_selected.connect(self._on_session_selected)
        self._session_popup.load(song_history.load_sessions(), self._session_id)
        self._session_popup.anchor_above(self._input_bar.history_button)
        self._session_popup.show()

    def _update_message_count(self) -> None:
        n = len(self._conversation.messages())
        self._msg_count_label.setText(f"{n} message{'' if n == 1 else 's'}" if n else "")
        self._msg_count_label.adjustSize()
        self._position_floating_controls()

    def _load_latest_session(self) -> None:
        """Load the most recent session, or start empty."""
        sessions = song_history.load_sessions()
        if sessions:
            latest = sessions[-1]
            self._session_id = latest["id"]
            self._conversation.clear()
            self._conversation.load_messages(latest["messages"])
            self._chat_view.load_history(
                self._conversation.messages(), self._rate_message
            )
        else:
            self._session_id = song_history.new_session_id()
            self._conversation.clear()
            self._chat_view.clear()
        self._update_message_count()

    # --- new chat ---
    def _on_new_chat(self) -> None:
        if self._session_id and self._conversation.messages():
            song_history.save_session(self._session_id, self._conversation.messages())
        self._session_id = song_history.new_session_id()
        self._conversation.clear()
        self._chat_view.clear()
        self._update_message_count()

    def _on_session_selected(self, session_id: str) -> None:
        if self._session_id and self._conversation.messages():
            song_history.save_session(self._session_id, self._conversation.messages())
        sessions = song_history.load_sessions()
        for s in sessions:
            if s["id"] == session_id:
                self._session_id = session_id
                self._conversation.clear()
                self._conversation.load_messages(s["messages"])
                self._chat_view.load_history(
                    self._conversation.messages(), self._rate_message
                )
                break
        self._update_message_count()

    # --- settings popup (opened from the macOS menu bar) ---
    def open_settings(self) -> None:
        if self._settings_popup is not None and self._settings_popup.isVisible():
            self._settings_popup.raise_()
            self._settings_popup.activateWindow()
            return
        self._settings_popup = SettingsPanel()
        self._settings_popup.history_cleared.connect(self._on_history_cleared)
        self._settings_popup.reset_window_requested.connect(self._on_reset_window)
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
        self._update_message_count()

        self._input_bar.set_enabled_inputs(False)

        self._worker = StreamWorker(self._conversation.to_api_format()[:-1])
        self._worker.chunk.connect(self._on_chunk)
        self._worker.status.connect(self._on_status)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.limit_reached.connect(self._on_limit_reached)
        self._worker.start()

    def _on_chunk(self, text: str) -> None:
        self._chat_view.append_to_assistant(text)
        self._conversation.append_to_last_assistant(text)

    def _on_status(self, text: str) -> None:
        self._chat_view.set_assistant_status(text)

    def _on_done(self, event_id: str = "", remaining: int = -1,
                 source_tier: str = "", sources: object = None,
                 locate_type: str = "", element: str = "",
                 walkthrough_steps: object = None) -> None:
        msg = self._conversation.last_assistant()
        self._chat_view.set_assistant_tier(source_tier, sources or [])
        if event_id and msg is not None:
            msg.event_id = event_id
            self._chat_view.show_rating(
                lambda value, m=msg: self._rate_message(m, value), initial=msg.rating
            )
        if walkthrough_steps:
            self._chat_view.setup_walkthrough_card(list(walkthrough_steps))
        elif locate_type == "navigation" and element:
            self._chat_view.setup_locate_affordance(element)
        self._chat_view.end_assistant_message()
        if self._session_id:
            song_history.save_session(self._session_id, self._conversation.messages())
        self._input_bar.set_remaining(remaining if remaining >= 0 else None)
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
            song_history.save_session(self._session_id, self._conversation.messages())

    def _on_history_cleared(self) -> None:
        self._session_id = song_history.new_session_id()
        self._conversation.clear()
        self._chat_view.clear()
        self._update_message_count()

    # --- update check ---
    def _start_update_check(self) -> None:
        from core.update_checker import UpdateChecker
        self._update_checker = UpdateChecker()
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.start()

    def _on_update_available(self, version: str) -> None:
        if self._update_popup is not None and self._update_popup.isVisible():
            return
        self._update_popup = _UpdatePopup(version)
        self._update_popup.get_clicked.connect(self._on_update_get)
        self._update_popup.center_on_screen()
        self._update_popup.show()

    def _on_update_get(self) -> None:
        from config import WEBSITE_URL
        QDesktopServices.openUrl(QUrl(WEBSITE_URL))
        if self._update_popup is not None:
            self._update_popup.close()

    def eventFilter(self, obj, event) -> bool:
        if (event.type() == QEvent.Type.KeyPress
                and event.key() in (Qt.Key_Return, Qt.Key_Enter)
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
        self._chat_view.append_to_assistant(f"\n\n[error] {display}")
        self._chat_view.end_assistant_message()
        self._input_bar.set_enabled_inputs(True)

    def _on_limit_reached(self, limit: int = -1) -> None:
        used = f"all {limit}" if limit and limit > 0 else "up all your"
        self._chat_view.append_to_assistant(
            f"\n\nYou've used {used} free messages. Thank you for using Conductor!"
        )
        self._chat_view.end_assistant_message()
        self._input_bar.set_remaining(0)
        self._input_bar.set_enabled_inputs(True)
