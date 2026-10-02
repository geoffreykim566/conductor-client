"""Chip: a label with its own always-on-top hover popup (native tooltips hide behind the window)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.theme import BORDER, BUTTON_RADIUS, FONT_XS, MONO, SURFACE, TEXT


class Chip(QLabel):
    """A QLabel with a custom hover popup instead of the native QToolTip.

    Native tooltips render *behind* this app's frameless, always-on-top main
    window on macOS (see README "Tooltips"), so this popup carries the same
    WindowStaysOnTopHint level itself.
    """

    def __init__(self, text: str, hover_text: str) -> None:
        super().__init__(text)
        self._hover_text = hover_text
        self._popup: QWidget | None = None
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event) -> None:
        if self._popup is None:
            # A translucent top-level window never paints its own stylesheet
            # background, so the box goes on a child (same as ui/popup.py).

            popup = QWidget()
            popup.setWindowFlags(
                Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                | Qt.Tool | Qt.WindowDoesNotAcceptFocus
            )
            popup.setAttribute(Qt.WA_TranslucentBackground)
            layout = QVBoxLayout(popup)
            layout.setContentsMargins(0, 0, 0, 0)
            card = QLabel(self._hover_text)
            card.setWordWrap(True)
            card.setFixedWidth(220)
            card.setStyleSheet(
                f"QLabel {{ background-color: {SURFACE}; color: {TEXT};"
                f" border: 1px solid {BORDER}; border-radius: {BUTTON_RADIUS}px;"
                f" font-family: {MONO}; font-size: {FONT_XS}px; padding: 6px 8px; }}"
            )
            layout.addWidget(card)
            self._popup = popup
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._popup.move(pos.x(), pos.y() + 4)
        self._popup.adjustSize()
        self._popup.show()
        self._popup.raise_()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self._popup is not None:
            self._popup.hide()
        super().leaveEvent(event)
