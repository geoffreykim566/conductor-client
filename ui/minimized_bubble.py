"""MinimizedBubble: the small draggable circle shown while the chat window is minimized."""
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from ui.theme import MINIMIZED_SIZE

if TYPE_CHECKING:
    from ui.chat_window import ChatWindow


class MinimizedBubble(QWidget):
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
