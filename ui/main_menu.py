"""The ☰ dropdown in the controls row: New chat, History, Settings, Report Bug."""
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from ui.glass import GlassBackdrop, full_rect
from ui.symbols import set_symbol
from ui.theme import ICON_SIZE, MENU_RADIUS, TEXT_SECONDARY

_ITEMS = (
    ("new_chat", "New Chat", "square.and.pencil", ICON_SIZE),
    ("history", "History", "clock.arrow.circlepath", ICON_SIZE),
    ("settings", "Settings", "gearshape", ICON_SIZE),
    ("report_bug", "Report Bug", "exclamationmark.triangle", ICON_SIZE),
)


class MainMenu(QWidget):
    """A glass dropdown; a click outside closes it (Qt.Popup). Emits `picked(key)`."""

    picked = Signal(str)

    def __init__(self) -> None:
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._panel = QWidget(self)
        self._panel.setObjectName("menuRoot")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._panel)

        layout = QVBoxLayout(self._panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(1)
        for key, label, symbol, size in _ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("menuItem")
            btn.setCursor(Qt.PointingHandCursor)
            set_symbol(btn, symbol, size, TEXT_SECONDARY)
            btn.setText(f"  {label}")   # set_symbol drops the text; the spaces pad it off the icon
            btn.clicked.connect(lambda _=False, k=key: self._pick(k))
            layout.addWidget(btn)

        self.setFixedWidth(170)
        self._glass = GlassBackdrop(self, full_rect(self, MENU_RADIUS), roots=[self._panel])

    def _pick(self, key: str) -> None:
        self.close()
        self.picked.emit(key)

    def show_below(self, anchor: QWidget) -> None:
        self.adjustSize()
        self.move(anchor.mapToGlobal(QPoint(0, anchor.height() + 6)))
        self.show()
