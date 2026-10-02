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
from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QPainter
from PySide6.QtWidgets import QApplication, QStackedWidget, QVBoxLayout, QWidget

from core.net.llm_client import MeWorker, StreamWorker
from core.state import song_history
from core.state.conversation import Conversation
from core.state.prefs import (
    clear_window_pos,
    clear_window_size,
    get_saved_window_pos,
    get_saved_window_size,
    reset_feedback_for_new_version,
    save_window_pos,
    save_window_size,
)
from ui.chat_prompts import ChatPromptsMixin
from ui.chat_sessions import ChatSessionsMixin
from ui.chat_turns import ChatTurnsMixin
from ui.chat_view import ChatView
from ui.input_bar import InputBar
from ui.minimized_bubble import MinimizedBubble
from ui.onboarding.feedback_dialog import FeedbackDialog
from ui.onboarding.update_popup import UpdatePopup
from ui.session_list import SessionListPanel
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


class ChatWindow(ChatTurnsMixin, ChatSessionsMixin, ChatPromptsMixin, QWidget):
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
        # With an app-wide stylesheet Qt paints an opaque default fill for any
        # widget without a rule; this window has none, so styled-background
        # painting is off to stay see-through (children keep theirs). The
        # backdrop panel is drawn in paintEvent instead (see README
        # "Translucent window").
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
        # No uniform spacing: the controls-to-chat_view gap is controls_row's
        # own bottom margin (input_bar.py), one lever instead of margin+spacing
        # stacking. chat_view-to-input_bar keeps its own explicit gap below.
        layout.setSpacing(0)

        # Built before being placed so its .controls widget (new-chat/history/
        # minimize/close) exists to add above the bubbles, on the backdrop panel.
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
        self._bubble: MinimizedBubble | None = None
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
        # Same look as #inputPanel (ui/style.py), drawn directly rather than
        # via a stylesheet rule (see the WA_StyledBackground comment in __init__).

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
            self._bubble = MinimizedBubble(self)
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
