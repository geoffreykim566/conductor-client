"""Input bar: pending attachment preview, new-chat/history icons, text input, send button.

Also doubles as the window's drag handle — clicking and dragging any part of
this bar's own background (not the text edit or a button) moves the window,
since the outer window no longer has a header to drag from.
"""
import base64

from PySide6.QtCore import QEvent, QPoint, Qt, Signal
from PySide6.QtGui import QFontMetrics, QKeyEvent, QMouseEvent, QPixmap, QTextOption
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class _ChatTextEdit(QTextEdit):
    """QTextEdit that sends on Enter and inserts newline on Shift+Enter."""

    submit = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submit.emit()
                return
        super().keyPressEvent(event)


class InputBar(QWidget):
    """Pending-attachment row + new-chat/history icons + text + send button.

    Emits send(text, list_of_b64_images) when the user submits.
    Emits enter_empty when Enter is pressed with no text (walkthrough advance).
    Emits new_chat_requested / history_requested from their respective icons.
    """

    send = Signal(str, list)
    enter_empty = Signal()
    new_chat_requested = Signal()
    history_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pending_images: list[str] = []
        self._drag_offset: QPoint | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 0, 10, 10)
        root.setSpacing(0)

        # Rounded, tinted backing panel behind the whole bar — same
        # transparent aesthetic as the message bubbles — with room at the
        # top for the attachment preview / remaining-count row to sit inside
        # it rather than floating loose above the pill.
        self._panel = QWidget()
        self._panel.setObjectName("inputPanel")
        self._panel.installEventFilter(self)
        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(10, 18, 10, 10)
        panel_layout.setSpacing(6)
        root.addWidget(self._panel)

        # Attachment preview row (hidden when empty)
        self._attachments_row = QWidget()
        self._attachments_layout = QHBoxLayout(self._attachments_row)
        self._attachments_layout.setContentsMargins(0, 0, 0, 0)
        self._attachments_layout.setSpacing(4)
        self._attachments_row.hide()
        panel_layout.addWidget(self._attachments_row)

        # Options row (above the input bubble)
        options_row = QHBoxLayout()
        options_row.setContentsMargins(2, 0, 2, 0)
        options_row.setSpacing(6)

        self._remaining_label = QLabel("")
        self._remaining_label.setObjectName("remainingLabel")
        self._remaining_label.hide()
        options_row.addWidget(self._remaining_label, 0, Qt.AlignVCenter)
        options_row.addStretch()

        panel_layout.addLayout(options_row)

        # Single rounded-rect bubble holding new-chat/history (left), the
        # text field, and send (right) — all the same height, so this is
        # the only boxed/backdropped element in the bar. options_row above
        # (remaining-message count, etc.) stays outside it, sitting on top.
        _CONTROL_SIZE = 32

        bubble = QWidget()
        bubble.setObjectName("inputBubble")
        bubble_row = QHBoxLayout(bubble)
        bubble_row.setContentsMargins(4, 4, 4, 4)
        bubble_row.setSpacing(4)

        new_btn = QPushButton("✦")
        new_btn.setObjectName("sendBtn")
        new_btn.setFixedSize(_CONTROL_SIZE, _CONTROL_SIZE)
        new_btn.clicked.connect(self.new_chat_requested)
        bubble_row.addWidget(new_btn)

        hist_btn = QPushButton("☰")
        hist_btn.setObjectName("sendBtn")
        hist_btn.setFixedSize(_CONTROL_SIZE, _CONTROL_SIZE)
        hist_btn.clicked.connect(self.history_requested)
        bubble_row.addWidget(hist_btn)
        self.history_button = hist_btn

        self._text = _ChatTextEdit()
        self._text.setObjectName("bareInput")
        self._text.setPlaceholderText("Ask anything about Logic Pro…")
        # QTextEdit's placeholder is painted from the document's default text
        # option, not the cursor-based setAlignment() — only the latter would
        # leave the placeholder left-aligned while typed text centers. That
        # option only covers horizontal alignment though — QTextDocument has
        # no concept of vertical centering, so the single line is vertically
        # centered manually via viewport margins sized from font metrics.
        self._text.document().setDefaultTextOption(QTextOption(Qt.AlignCenter))
        self._text.document().setDocumentMargin(0)
        self._text.setFixedHeight(_CONTROL_SIZE)
        line_height = QFontMetrics(self._text.font()).height()
        top_margin = max(0, (_CONTROL_SIZE - line_height) // 2)
        self._text.setViewportMargins(4, top_margin, 4, 0)
        self._text.submit.connect(self._on_send)
        bubble_row.addWidget(self._text, 1)

        self._send_btn = QPushButton("↑")
        self._send_btn.setObjectName("sendBtn")
        self._send_btn.setFixedSize(_CONTROL_SIZE, _CONTROL_SIZE)
        self._send_btn.clicked.connect(self._on_send)
        bubble_row.addWidget(self._send_btn)

        panel_layout.addWidget(bubble)

    def add_pending_image(self, b64: str) -> None:
        """Add an image to the pending attachments preview."""
        self._pending_images.append(b64)
        idx = len(self._pending_images) - 1

        thumb_container = QWidget()
        layout = QVBoxLayout(thumb_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        pix = QPixmap()
        pix.loadFromData(base64.b64decode(b64), "PNG")
        thumb = QLabel()
        thumb.setPixmap(pix.scaledToHeight(40, Qt.SmoothTransformation))
        thumb.setStyleSheet("border: 1px solid #444; border-radius: 3px;")
        layout.addWidget(thumb)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedHeight(14)
        remove_btn.setStyleSheet("font-size: 9px;")
        remove_btn.clicked.connect(lambda _=False, i=idx: self._remove_pending(i))
        layout.addWidget(remove_btn)

        self._attachments_layout.addWidget(thumb_container)
        self._attachments_row.show()

    def set_remaining(self, remaining: int | None) -> None:
        """Show how many free messages the user has left, or hide when unknown."""
        if remaining is None or remaining < 0:
            self._remaining_label.hide()
            return
        noun = "message" if remaining == 1 else "messages"
        self._remaining_label.setText(f"{remaining} {noun} left")
        self._remaining_label.show()

    def set_enabled_inputs(self, enabled: bool) -> None:
        self._text.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)

    def _on_send(self) -> None:
        text = self._text.toPlainText().strip()
        if not text:
            self.enter_empty.emit()
            return
        images = list(self._pending_images)
        self._pending_images.clear()
        self._clear_attachments_ui()
        self._text.clear()
        self.send.emit(text, images)

    def _remove_pending(self, idx: int) -> None:
        if 0 <= idx < len(self._pending_images):
            self._pending_images.pop(idx)
            self._rebuild_attachments_ui()

    def _clear_attachments_ui(self) -> None:
        while self._attachments_layout.count():
            item = self._attachments_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._attachments_row.hide()

    def _rebuild_attachments_ui(self) -> None:
        images = list(self._pending_images)
        self._pending_images.clear()
        self._clear_attachments_ui()
        for b64 in images:
            self.add_pending_image(b64)

    # --- window drag ---
    # Only fires when the click lands on background with no interactive
    # child under it (Qt routes events to a child widget first when one is
    # under the cursor), so text selection in the input and the icon/send
    # buttons are unaffected. `_panel` is a separate child widget covering
    # most of the bar, so it needs its own event filter below — a plain
    # override here only catches the thin margin outside `_panel`.
    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._drag_press(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._drag_move(event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_release()
        super().mouseReleaseEvent(event)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._panel:
            t = event.type()
            if t == QEvent.Type.MouseButtonPress:
                self._drag_press(event)
            elif t == QEvent.Type.MouseMove:
                self._drag_move(event)
            elif t == QEvent.Type.MouseButtonRelease:
                self._drag_release()
        return super().eventFilter(obj, event)

    def _drag_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()

    def _drag_move(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)

    def _drag_release(self) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            if hasattr(self.window(), "persist_geometry"):
                self.window().persist_geometry()
