"""Scrolling chat history view."""
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QGraphicsEffect, QLabel, QScrollArea, QVBoxLayout, QWidget

from ui.message_widget import MessageWidget

MONO = '"Menlo", monospace'

_FADE_HEIGHT = 40  # roughly where the old drag-header used to be
_GROWTH_BUDGET_PX = 110  # how far a streaming response can push the view
# down before it freezes and later chunks just accumulate below the fold —
# a pixel budget rather than a line count, since these narrow bubbles wrap
# to noticeably shorter lines than a line-count estimate would assume.


class _TopEdgeFadeEffect(QGraphicsEffect):
    """Fades the widget's own rendered content to nothing at its top edge —
    erases pixel alpha rather than painting a color over it, so what's
    revealed is the window's real transparency (Logic Pro/desktop showing
    through), not a tinted overlay."""

    def draw(self, painter: QPainter) -> None:
        result_pair = self.sourcePixmap(Qt.CoordinateSystem.LogicalCoordinates)
        if isinstance(result_pair, tuple):
            pixmap, offset = result_pair
        else:
            pixmap, offset = result_pair, QPoint(0, 0)
        if pixmap.isNull():
            painter.drawPixmap(offset, pixmap)
            return

        fade_h = min(_FADE_HEIGHT, pixmap.height())
        if fade_h <= 0:
            painter.drawPixmap(offset, pixmap)
            return

        result = pixmap.copy()
        p = QPainter(result)
        gradient = QLinearGradient(0, 0, 0, fade_h)
        gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 255))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        p.fillRect(0, 0, result.width(), fade_h, gradient)
        p.end()

        painter.drawPixmap(offset, result)


class ChatView(QWidget):
    """Scrollable column of MessageWidget bubbles with an empty-state placeholder."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setGraphicsEffect(_TopEdgeFadeEffect(self))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── placeholder shown when chat is empty ──────────────────
        self._placeholder = QLabel("")
        self._placeholder.setObjectName("chatPlaceholder")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setWordWrap(True)
        outer.addWidget(self._placeholder, 1)

        # ── scrollable message list ───────────────────────────────
        # QScrollArea's internal viewport (a separate child widget Qt
        # creates under the hood) has autoFillBackground on by default,
        # painting an opaque palette color — the transparent rule in the
        # app stylesheet only reaches the QScrollArea frame itself, not the
        # viewport, so without this the whole scroll region shows up as a
        # solid backdrop behind the message bubbles. A plain widget
        # attribute (not a stylesheet rule) so it can't affect how the
        # QApplication stylesheet colors the message bubbles underneath.
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.viewport().setAutoFillBackground(False)

        self._container = QWidget()
        self._container.setAutoFillBackground(False)
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 14, 0, 0)
        self._layout.setSpacing(2)
        # Leading stretch absorbs leftover space above the messages, so a
        # short conversation sits flush against the input bar at the bottom
        # (like a normal chat log) instead of floating near the top with
        # dead space below it. Re-added by clear() since takeAt() drops it.
        self._layout.addStretch()
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
        self._layout.addStretch()
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
        QTimer.singleShot(0, self._apply_scroll)

    def _apply_scroll(self) -> None:
        # Once the streaming assistant bubble's own rendered height passes
        # the growth budget, this stops updating the scrollbar at all —
        # leaving it exactly where it was — so later chunks just extend the
        # bubble below the frozen view instead of dragging its (already-
        # read) top further up. Checking the bubble's actual height rather
        # than capping a scroll-position offset avoids a blind spot: while
        # the conversation still fits the viewport the scrollbar doesn't
        # move at all (value stuck at 0), so an offset-based budget could
        # let the bubble grow far past it before any capping ever kicked in.
        if (self._current_assistant is not None
                and self._current_assistant.height() > _GROWTH_BUDGET_PX):
            return
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
