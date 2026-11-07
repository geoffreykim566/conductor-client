"""VoiceToast: a short message in a small glass bubble above the mic pill, gone after a few
seconds or a click elsewhere. Used when the box has text (else the message is the placeholder)."""
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.glass import GlassBackdrop, full_rect
from ui.theme import MENU_RADIUS

_SHOW_MS = 4000


class VoiceToast(QWidget):
    _open: "VoiceToast | None" = None   # one at a time

    def __init__(self, text: str) -> None:
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        panel = QWidget(self)
        panel.setObjectName("menuRoot")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(panel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 6, 10, 6)
        label = QLabel(text)
        label.setObjectName("voiceToastText")
        layout.addWidget(label)
        self._glass = GlassBackdrop(self, full_rect(self, MENU_RADIUS), roots=[panel])
        QTimer.singleShot(_SHOW_MS, self.close)

    @classmethod
    def show_above(cls, anchor: QWidget, text: str) -> None:
        """Right edge on the anchor's right edge, just above it."""
        if cls._open is not None:
            cls._open.close()
        toast = cls(text)
        cls._open = toast
        toast.adjustSize()
        corner = anchor.mapToGlobal(QPoint(anchor.width(), 0))
        toast.move(corner.x() - toast.width(), corner.y() - toast.height() - 6)
        toast.show()

    @classmethod
    def hide_open(cls) -> None:
        if cls._open is not None:
            cls._open.close()

    def closeEvent(self, event) -> None:
        if VoiceToast._open is self:
            VoiceToast._open = None
        super().closeEvent(event)
