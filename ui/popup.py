"""Reusable frameless/translucent popup window.

Used for Settings and its confirm dialogs (delete history / uninstall), centered
on screen.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.glass import GlassBackdrop, full_rect
from ui.motion import fade_window_in
from ui.symbols import set_symbol
from ui.theme import ICON_BTN_SIZE, ICON_SIZE, POPUP_RADIUS, TEXT_SECONDARY


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
        close_btn.setFixedSize(ICON_BTN_SIZE, ICON_BTN_SIZE)
        close_btn.clicked.connect(self._on_close)
        set_symbol(close_btn, "xmark", ICON_SIZE - 1, TEXT_SECONDARY)
        hl.addWidget(close_btn)
        panel_layout.addWidget(header)

        self.body = QWidget()
        panel_layout.addWidget(self.body, 1)

        self._glass = GlassBackdrop(self, full_rect(self, POPUP_RADIUS), roots=[self._panel])

    def _on_close(self) -> None:
        self.closed.emit()
        self.close()

    def _sync_panel_size(self) -> None:
        self._panel.setFixedSize(self.size())

    def resizeEvent(self, event) -> None:
        self._sync_panel_size()
        super().resizeEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        fade_window_in(self)
        # Without this, a popup that isn't yet the active/key window can eat its
        # first click just activating the window (macOS), so e.g. the X button
        # doesn't register until a second click.
        self.raise_()
        self.activateWindow()

    def center_on_screen(self) -> None:
        self.adjustSize()
        self._sync_panel_size()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )
