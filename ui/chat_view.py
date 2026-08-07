"""Scrolling chat history view."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ui.message_widget import MessageWidget

MONO = '"Menlo", monospace'


class ChatView(QWidget):
    """Scrollable column of MessageWidget bubbles with an empty-state placeholder."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── placeholder shown when chat is empty ──────────────────
        self._placeholder = QLabel("Ask anything about your Logic Pro session.")
        self._placeholder.setObjectName("chatPlaceholder")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setWordWrap(True)
        outer.addWidget(self._placeholder, 1)

        # ── scrollable message list ───────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QScrollArea.NoFrame)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignTop)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll, 1)

        self._current_assistant: MessageWidget | None = None
        self._active_wt_widget: MessageWidget | None = None
        self._scroll.hide()

    def add_user_message(self, text: str, images_b64: list[str]) -> None:
        self._show_messages()
        widget = MessageWidget("user", text=text, images_b64=images_b64)
        self._layout.addWidget(widget)
        self._scroll_to_bottom()

    def begin_assistant_message(self) -> None:
        self._show_messages()
        self._current_assistant = MessageWidget("assistant", text="")
        self._layout.addWidget(self._current_assistant)
        self._scroll_to_bottom()

    def append_to_assistant(self, chunk: str) -> None:
        if self._current_assistant is None:
            return
        self._current_assistant.append_text(chunk)
        self._scroll_to_bottom()

    def set_assistant_status(self, text: str) -> None:
        if self._current_assistant is not None:
            self._current_assistant.set_status_text(text)

    def set_assistant_tier(self, tier: str, sources: list) -> None:
        if self._current_assistant is not None:
            self._current_assistant.set_source_tier(tier)
            self._current_assistant.set_sources(sources)

    def setup_locate_affordance(self, element: str) -> None:
        if self._current_assistant is not None:
            self._current_assistant.setup_locate(element)

    def setup_walkthrough_card(self, steps: list) -> None:
        if self._current_assistant is not None:
            self._current_assistant.setup_walkthrough(steps)
            self._active_wt_widget = self._current_assistant

    def wt_enter(self) -> None:
        if self._active_wt_widget is not None:
            self._active_wt_widget.wt_enter()

    def has_active_walkthrough(self) -> bool:
        return self._active_wt_widget is not None

    def force_end_active_walkthrough(self) -> None:
        """Safety hook for app quit — stop any running walkthrough thread
        before QApplication teardown destroys it (see clear())."""
        if self._active_wt_widget is not None:
            self._active_wt_widget.force_end_walkthrough()

    def show_rating(self, on_rate, initial: int = 0) -> None:
        if self._current_assistant is not None:
            self._current_assistant.enable_rating(on_rate, initial=initial)

    def end_assistant_message(self) -> None:
        self._current_assistant = None

    def clear(self) -> None:
        # Stop any running walkthrough thread before its owning widget gets
        # deleteLater()'d below — Qt6 aborts the process if a QThread is
        # still running when its QObject is destroyed.
        if self._active_wt_widget is not None:
            self._active_wt_widget.force_end_walkthrough()
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._current_assistant = None
        self._active_wt_widget = None
        self._scroll.hide()
        self._placeholder.show()

    def load_history(self, messages: list, on_rate=None) -> None:
        self.clear()
        for msg in messages:
            widget = MessageWidget(msg.role, text=msg.text, images_b64=[])
            self._layout.addWidget(widget)
            if on_rate and msg.role == "assistant" and msg.event_id:
                widget.enable_rating(
                    lambda v, m=msg: on_rate(m, v), initial=msg.rating
                )
        if messages:
            self._show_messages()
        self._scroll_to_bottom()

    def _show_messages(self) -> None:
        self._placeholder.hide()
        self._scroll.show()

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(
            0,
            lambda: self._scroll.verticalScrollBar().setValue(
                self._scroll.verticalScrollBar().maximum()
            ),
        )
