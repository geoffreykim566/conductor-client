"""Main floating chat window. Frameless, always-on-top, minimizes to a small bubble."""
from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QStackedWidget,
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
from core.window_capture import capture_fl_studio_window
from ui.chat_view import ChatView
from ui.input_bar import InputBar
from ui.session_list import SessionListPanel
from ui.setup_screen import (
    FeedbackDialog,
    clear_window_pos,
    get_saved_window_pos,
    get_saved_window_size,
    is_feedback_never_show,
    reset_feedback_for_new_version,
    save_window_pos,
)
from ui.settings_panel import SettingsPanel

MONO = '"Menlo", monospace'

STYLESHEET = f"""
QWidget#root {{
    background-color: #141415;
    border: 1px solid #2a2a2c;
    border-radius: 14px;
}}
QWidget#minimizedRoot {{
    background-color: #141415;
    border: 1px solid #2a2a2c;
    border-radius: 30px;
}}
QWidget#headerBar {{
    border-bottom: 1px solid #222224;
}}
QWidget#updateBanner {{
    background-color: #0f1f38;
    border-bottom: 1px solid #1a3a6a;
}}
QLabel#updateLabel {{
    color: #ebebf5;
    font-family: {MONO};
    font-size: 11px;
}}
QPushButton#updateGetBtn {{
    background-color: #0a84ff;
    color: white;
    border: none;
    border-radius: 4px;
    font-family: {MONO};
    font-size: 10px;
    font-weight: 600;
    padding: 2px 8px;
    min-height: 20px;
}}
QPushButton#updateGetBtn:hover {{
    background-color: #409cff;
}}
QLabel#header {{
    color: #636366;
    font-family: {MONO};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.8px;
    padding: 0 2px;
    text-transform: uppercase;
}}
QPushButton#headerBtn {{
    background: transparent;
    color: #48484a;
    border: none;
    font-size: 13px;
    font-family: {MONO};
    padding: 0;
}}
QPushButton#headerBtn:hover {{
    color: #ebebf5;
}}
QFrame#userBubble {{
    background-color: #0a84ff;
    border-radius: 16px;
}}
QFrame#userBubble QLabel {{
    color: #ffffff;
}}
QFrame#assistantBubble {{
    background-color: #1c1c1e;
    border-radius: 16px;
    border: 1px solid #2c2c2e;
}}
QFrame#assistantBubble QLabel {{
    color: #ebebf5;
}}
QTextEdit {{
    background-color: #1c1c1e;
    color: #ebebf5;
    border: 1px solid #38383a;
    border-radius: 10px;
    padding: 6px 10px;
    font-family: {MONO};
    font-size: 12px;
}}
QTextEdit:focus {{
    border: 1px solid #48484a;
}}
QPushButton {{
    background-color: #2c2c2e;
    color: #ebebf5;
    border: 1px solid #38383a;
    border-radius: 6px;
    font-family: {MONO};
    font-size: 11px;
}}
QPushButton:hover {{
    background-color: #38383a;
}}
QPushButton:disabled {{
    color: #3a3a3c;
}}
QPushButton#sendBtn {{
    background-color: #0a84ff;
    color: #ffffff;
    border: none;
    border-radius: 16px;
    font-size: 15px;
}}
QPushButton#sendBtn:hover {{
    background-color: #409cff;
}}
QPushButton#sendBtn:disabled {{
    background-color: #2c2c2e;
    color: #3a3a3c;
}}
QPushButton#captureBox {{
    background: transparent;
    border: 1px solid #48484a;
    border-radius: 4px;
    color: transparent;
    font-size: 9px;
    font-weight: bold;
    padding: 0;
}}
QPushButton#captureBox:checked {{
    background: #0a84ff;
    border: 1px solid #0a84ff;
    color: #ffffff;
}}
QPushButton#captureLabel {{
    background: transparent;
    border: none;
    color: #8e8e93;
    font-family: {MONO};
    font-size: 10px;
    padding: 0;
    text-align: left;
}}
QPushButton#captureLabel:hover {{
    color: #ebebf5;
}}
QLabel#remainingLabel {{
    background: transparent;
    color: #636366;
    font-family: {MONO};
    font-size: 10px;
}}
QPushButton#rateBtn {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    font-size: 12px;
    padding: 0;
}}
QPushButton#rateBtn:hover {{
    background: #1c1c1e;
    border: 1px solid #2c2c2e;
}}
QPushButton#rateBtn[selected="true"] {{
    background: #2c2c2e;
    border: 1px solid #0a84ff;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #38383a;
    border-radius: 2px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QPushButton#bubble {{
    background-color: #0a84ff;
    color: white;
    border-radius: 30px;
    font-size: 24px;
    border: none;
}}
QPushButton#bubble:hover {{
    background-color: #409cff;
}}
QPushButton#danger {{
    background-color: #2a1515;
    color: #ff453a;
    border: 1px solid #3a2020;
    border-radius: 6px;
    font-family: {MONO};
    font-size: 11px;
    padding: 6px;
}}
QPushButton#danger:hover {{
    background-color: #ff453a;
    color: #ffffff;
    border-color: #ff453a;
}}
QToolTip {{
    background-color: #2c2c2e;
    color: #ebebf5;
    border: 1px solid #48484a;
    border-radius: 6px;
    padding: 4px 8px;
    font-family: {MONO};
    font-size: 11px;
}}
QWidget#sessionHeader {{
    border-bottom: 1px solid #222224;
}}
QLabel#sessionTitle {{
    color: #636366;
    font-family: {MONO};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.8px;
}}
QFrame#sessionRow {{
    border-bottom: 1px solid #222224;
    background: transparent;
}}
QFrame#sessionRow:hover {{
    background: #1c1c1e;
}}
QFrame#sessionRowActive {{
    border-bottom: 1px solid #222224;
    border-left: 3px solid #0a84ff;
    background: #1a2640;
}}
QLabel#sessionDate {{
    color: #ebebf5;
    font-family: {MONO};
    font-size: 11px;
    font-weight: 600;
}}
QLabel#sessionPreview {{
    color: #636366;
    font-size: 12px;
}}
QLabel#sessionEmpty {{
    color: #48484a;
    font-family: {MONO};
    font-size: 11px;
    padding: 32px;
}}
QPushButton#showMeBtn {{
    background: transparent;
    border: 1px solid #38383a;
    border-radius: 6px;
    color: #0a84ff;
    font-family: {MONO};
    font-size: 10px;
    font-weight: 600;
    padding: 3px 8px;
}}
QPushButton#showMeBtn:hover {{
    border-color: #0a84ff;
    background: #0f1f3a;
}}
QPushButton#showMeBtn:disabled {{
    color: #48484a;
    border-color: #2c2c2e;
}}
QLabel#chatPlaceholder {{
    color: #3a3a3c;
    font-family: {MONO};
    font-size: 11px;
    padding: 32px;
}}
QLineEdit {{
    background-color: #1c1c1e;
    color: #ebebf5;
    border: 1px solid #38383a;
    border-radius: 8px;
    padding: 8px 10px;
    font-family: {MONO};
    font-size: 12px;
}}
QLineEdit:focus {{
    border: 1px solid #48484a;
}}
QPushButton#primary {{
    background-color: #0a84ff;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 9px;
    font-family: {MONO};
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background-color: #409cff; }}
QPushButton#primary:disabled {{ background-color: #2c2c2e; color: #48484a; }}
QPushButton#secondary {{
    background-color: #2c2c2e;
    color: #ebebf5;
    border: 1px solid #38383a;
    border-radius: 8px;
    padding: 9px;
    font-family: {MONO};
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#secondary:hover {{ background-color: #38383a; }}
QLabel#error {{
    color: #ff453a;
    font-family: {MONO};
    font-size: 11px;
}}
"""


class _UpdateBanner(QWidget):
    dismissed = Signal()
    get_clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("updateBanner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 8, 5)
        layout.setSpacing(8)

        self._label = QLabel()
        self._label.setObjectName("updateLabel")
        layout.addWidget(self._label, 1)

        get_btn = QPushButton("Get")
        get_btn.setObjectName("updateGetBtn")
        get_btn.setFixedHeight(22)
        get_btn.clicked.connect(self.get_clicked)
        layout.addWidget(get_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("headerBtn")
        close_btn.setFixedSize(20, 20)
        close_btn.clicked.connect(self.dismissed)
        layout.addWidget(close_btn)

    def set_version(self, version: str) -> None:
        self._label.setText(f"Update available — v{version}")


class _DragHeader(QWidget):
    """Header bar that lets the user drag the window."""

    reset_key_requested = Signal()
    new_chat_requested = Signal()
    history_requested = Signal()

    def __init__(self, parent_window: "ChatWindow") -> None:
        super().__init__()
        self.setObjectName("headerBar")
        self._parent_window = parent_window
        self._drag_offset: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        gear_btn = QPushButton("⚙")
        gear_btn.setObjectName("headerBtn")
        gear_btn.setFixedSize(20, 20)
        gear_btn.setToolTip("Settings")
        gear_btn.clicked.connect(self.reset_key_requested)
        layout.addWidget(gear_btn)

        new_btn = QPushButton("✦")
        new_btn.setObjectName("headerBtn")
        new_btn.setFixedSize(20, 20)
        new_btn.setToolTip("New chat")
        new_btn.clicked.connect(self.new_chat_requested)
        layout.addWidget(new_btn)

        hist_btn = QPushButton("☰")
        hist_btn.setObjectName("headerBtn")
        hist_btn.setFixedSize(20, 20)
        hist_btn.setToolTip("Past chats")
        hist_btn.clicked.connect(self.history_requested)
        layout.addWidget(hist_btn)

        title = QLabel("Conductor-Logic-Pro-v1")
        title.setObjectName("header")
        layout.addWidget(title)
        layout.addStretch()

        min_btn = QPushButton("—")
        min_btn.setObjectName("headerBtn")
        min_btn.setFixedSize(20, 20)
        min_btn.clicked.connect(parent_window.minimize_to_bubble)
        layout.addWidget(min_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("headerBtn")
        close_btn.setFixedSize(20, 20)
        close_btn.clicked.connect(parent_window.hide_to_dock)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self._parent_window.pos()
            )

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self._parent_window.move(
                event.globalPosition().toPoint() - self._drag_offset
            )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None


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


_PAGE_CHAT = 0
_PAGE_HISTORY = 1
_PAGE_SETTINGS = 2


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
        saved = get_saved_window_size()
        if saved:
            self.setFixedSize(saved[0], saved[1])
        else:
            self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
            self.setMaximumSize(MAX_WINDOW_WIDTH, MAX_WINDOW_HEIGHT)
            self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self._conversation = Conversation()
        self._worker: StreamWorker | None = None
        self._me_worker: MeWorker | None = None
        self._session_id: str | None = None

        # Root with rounded background
        self._root = QWidget(self)
        self._root.setObjectName("root")
        self._root.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)

        layout = QVBoxLayout(self._root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = _DragHeader(self)
        self._header.reset_key_requested.connect(self._on_reset_key)
        self._header.new_chat_requested.connect(self._on_new_chat)
        self._header.history_requested.connect(self._on_toggle_history)
        layout.addWidget(self._header)

        self._update_banner = _UpdateBanner()
        self._update_banner.get_clicked.connect(self._on_update_get)
        self._update_banner.dismissed.connect(self._on_update_dismissed)
        self._update_banner.hide()
        layout.addWidget(self._update_banner)

        self._stack = QStackedWidget()
        self._chat_view = ChatView()
        self._session_panel = SessionListPanel()
        self._settings_panel = SettingsPanel()
        self._stack.addWidget(self._chat_view)        # index 0
        self._stack.addWidget(self._session_panel)    # index 1
        self._stack.addWidget(self._settings_panel)   # index 2
        layout.addWidget(self._stack, 1)

        self._session_panel.session_selected.connect(self._on_session_selected)
        self._session_panel.closed.connect(self._show_chat)
        self._settings_panel.closed.connect(self._show_chat)
        self._settings_panel.history_cleared.connect(self._on_history_cleared)
        self._settings_panel.reset_size_requested.connect(self._on_reset_size)
        self._settings_panel.size_locked.connect(self._on_size_locked)
        self._settings_panel.size_unlocked.connect(self._on_size_unlocked)

        self._input_bar = InputBar()
        self._input_bar.send.connect(self._on_user_send)
        self._input_bar.enter_empty.connect(self._on_enter_empty)
        layout.addWidget(self._input_bar)

        QApplication.instance().installEventFilter(self)

        self.setStyleSheet(STYLESHEET)

        self._grip = QSizeGrip(self._root)
        self._grip.setFixedSize(16, 16)
        self._grip.setStyleSheet("QSizeGrip { background: transparent; }")
        self._grip.raise_()
        self._grip.move(self.width() - 16, self.height() - 16)
        if get_saved_window_size():
            self._grip.hide()

        self._feedback_dialog: FeedbackDialog | None = None
        self._bubble: _MinimizedBubble | None = None
        saved_pos = get_saved_window_pos()
        if saved_pos and QGuiApplication.screenAt(QPoint(saved_pos[0], saved_pos[1])):
            self.move(saved_pos[0], saved_pos[1])
        else:
            self._anchor_to_bottom_right()
        self._load_latest_session()
        self._refresh_remaining()
        self._update_checker = None
        self._start_update_check()
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(6 * 60 * 60 * 1000)  # every 6 hours
        self._update_timer.timeout.connect(self._start_update_check)
        self._update_timer.start()

    # --- resize ---
    def resizeEvent(self, event) -> None:
        w, h = event.size().width(), event.size().height()
        self._root.setGeometry(0, 0, w, h)
        self._grip.move(w - self._grip.width(), h - self._grip.height())
        if self._stack.currentIndex() == _PAGE_SETTINGS:
            self._settings_panel.set_window_size(w, h)
        super().resizeEvent(event)

    def _on_reset_size(self) -> None:
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._anchor_to_bottom_right()

    def _on_size_locked(self, w: int, h: int) -> None:
        self.setFixedSize(w, h)
        self._grip.hide()
        save_window_pos(self.x(), self.y())

    def _on_size_unlocked(self) -> None:
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.setMaximumSize(MAX_WINDOW_WIDTH, MAX_WINDOW_HEIGHT)
        self._grip.show()
        clear_window_pos()

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

    def hide_to_dock(self) -> None:
        if self._bubble is not None:
            self._bubble.hide()
        self.hide()

    def open_from_dock(self) -> None:
        if self._bubble is not None:
            self._bubble.hide()
        self.show()
        self.raise_()
        self.activateWindow()

    # --- stack helpers ---
    def _show_chat(self) -> None:
        self._stack.setCurrentIndex(_PAGE_CHAT)
        self._input_bar.set_enabled_inputs(True)

    def _show_history(self) -> None:
        sessions = song_history.load_sessions()
        self._session_panel.load(sessions, self._session_id)
        self._stack.setCurrentIndex(_PAGE_HISTORY)
        self._input_bar.set_enabled_inputs(False)

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

    # --- new chat ---
    def _on_new_chat(self) -> None:
        if self._session_id and self._conversation.messages():
            song_history.save_session(self._session_id, self._conversation.messages())
        self._session_id = song_history.new_session_id()
        self._conversation.clear()
        self._chat_view.clear()
        self._show_chat()

    # --- history panel ---
    def _on_toggle_history(self) -> None:
        if self._stack.currentIndex() == _PAGE_HISTORY:
            self._show_chat()
        else:
            self._show_history()

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
        self._show_chat()

    # --- remaining-messages counter ---
    def _refresh_remaining(self) -> None:
        """Fetch the user's free-tier usage in the background and update the input bar."""
        self._me_worker = MeWorker()
        self._me_worker.loaded.connect(self._input_bar.set_remaining)
        self._me_worker.start()

    # --- send ---
    def _on_user_send(self, text: str, images_b64: list[str]) -> None:
        # Silently capture Logic Pro for visual context, unless the user opted out.
        if self._input_bar.capture_enabled():
            try:
                images_b64 = [capture_fl_studio_window()] + images_b64
            except Exception:
                pass

        self._chat_view.add_user_message(text, images_b64)
        self._conversation.add_user(text, images_b64)

        self._chat_view.begin_assistant_message()
        self._conversation.add_assistant("")

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
        self._show_chat()

    def _on_reset_key(self) -> None:
        self._settings_panel.refresh()
        self._settings_panel.set_window_size(self.width(), self.height())
        self._stack.setCurrentIndex(_PAGE_SETTINGS)
        self._input_bar.set_enabled_inputs(False)

    # --- update check ---
    def _start_update_check(self) -> None:
        from core.update_checker import UpdateChecker
        self._update_checker = UpdateChecker()
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.start()

    def _on_update_available(self, version: str) -> None:
        self._update_banner.set_version(version)
        self._update_banner.show()

    def _on_update_dismissed(self) -> None:
        self._update_banner.hide()

    def _on_update_get(self) -> None:
        from config import WEBSITE_URL
        QDesktopServices.openUrl(QUrl(WEBSITE_URL))

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
            display = "Invalid API key. Click ⚙ in the top-right to reset it."
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
