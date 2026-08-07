"""Reusable frameless/translucent popup window.

Used for Settings, its confirm dialogs (delete history / uninstall), and the
launch-time update prompt — all centered on screen. History uses the same
base but anchors above a button instead of centering (see anchor_above).
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class Popup(QWidget):
    """Frameless, translucent, always-on-top popup with a titled header + close button.

    Subclasses (or callers) add their own content to `self.body`.
    """

    closed = Signal()

    def __init__(self, title: str, width: int) -> None:
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(width)

        self._panel = QWidget(self)
        self._panel.setObjectName("popupRoot")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._panel)

        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("sessionHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 8, 12, 8)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("sessionTitle")
        hl.addWidget(title_lbl)
        hl.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setObjectName("headerBtn")
        close_btn.setFixedSize(20, 20)
        close_btn.clicked.connect(self._on_close)
        hl.addWidget(close_btn)
        panel_layout.addWidget(header)

        self.body = QWidget()
        panel_layout.addWidget(self.body, 1)

    def _on_close(self) -> None:
        self.closed.emit()
        self.close()

    def _sync_panel_size(self) -> None:
        self._panel.setFixedSize(self.size())

    def resizeEvent(self, event) -> None:
        self._sync_panel_size()
        super().resizeEvent(event)

    def center_on_screen(self) -> None:
        self.adjustSize()
        self._sync_panel_size()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )

    def anchor_above(self, widget: QWidget, gap: int = 8) -> None:
        """Position this popup's bottom edge `gap` px above `widget`'s top edge,
        right-aligned to `widget`'s right edge, clamped to stay on screen."""
        self.adjustSize()
        self._sync_panel_size()
        top_left = widget.mapToGlobal(widget.rect().topLeft())
        x = top_left.x() + widget.width() - self.width()
        y = top_left.y() - self.height() - gap
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = max(screen.left(), min(x, screen.right() - self.width()))
        y = max(screen.top(), y)
        self.move(x, y)
