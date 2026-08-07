"""Input bar: pending attachment preview, text input, and three action buttons."""
import base64

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QPixmap
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
    """Pending-attachment row + text + buttons.

    Emits send(text, list_of_b64_images) when the user submits.
    Emits enter_empty when Enter is pressed with no text (walkthrough advance).
    """

    send = Signal(str, list)
    enter_empty = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pending_images: list[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 6, 10, 10)
        root.setSpacing(6)

        # Attachment preview row (hidden when empty)
        self._attachments_row = QWidget()
        self._attachments_layout = QHBoxLayout(self._attachments_row)
        self._attachments_layout.setContentsMargins(0, 0, 0, 0)
        self._attachments_layout.setSpacing(4)
        self._attachments_row.hide()
        root.addWidget(self._attachments_row)

        # Options bar (above the input bubble)
        options_row = QHBoxLayout()
        options_row.setContentsMargins(2, 0, 2, 0)
        options_row.setSpacing(6)

        self._remaining_label = QLabel("")
        self._remaining_label.setObjectName("remainingLabel")
        self._remaining_label.hide()
        options_row.addWidget(self._remaining_label, 0, Qt.AlignVCenter)

        options_row.addStretch()

        self._capture_box = QPushButton("✓")
        self._capture_box.setObjectName("captureBox")
        self._capture_box.setCheckable(True)
        self._capture_box.setChecked(True)
        self._capture_box.setFixedSize(14, 14)
        self._capture_box.setCursor(Qt.PointingHandCursor)
        self._capture_box.setToolTip("Attach a screenshot of Logic Pro with your message")
        options_row.addWidget(self._capture_box, 0, Qt.AlignVCenter)

        self._capture_label = QPushButton("Include screenshot")
        self._capture_label.setObjectName("captureLabel")
        self._capture_label.setCursor(Qt.PointingHandCursor)
        self._capture_label.clicked.connect(self._capture_box.toggle)
        options_row.addWidget(self._capture_label, 0, Qt.AlignVCenter)

        root.addLayout(options_row)

        # Input + buttons row
        input_row = QHBoxLayout()
        input_row.setSpacing(4)

        self._text = _ChatTextEdit()
        self._text.setPlaceholderText("Ask anything about Logic Pro…")
        self._text.setFixedHeight(64)
        self._text.submit.connect(self._on_send)
        input_row.addWidget(self._text)

        self._send_btn = QPushButton("↑")
        self._send_btn.setObjectName("sendBtn")
        self._send_btn.setFixedSize(32, 32)
        self._send_btn.setToolTip("Send")
        self._send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self._send_btn, 0, Qt.AlignBottom)
        root.addLayout(input_row)

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

    def capture_enabled(self) -> bool:
        """Whether to attach a Logic Pro screenshot to the next message."""
        return self._capture_box.isChecked()

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
