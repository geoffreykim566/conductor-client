"""MicPill: the voice control on the Explain row. One pill, split about 2:1 into the mic (start /
stop) and a chevron that opens the input menu. No divider: hovering a part fills only that part,
which is what shows the split. The pill paints its own outline and fills (README "Mic pill")."""
from PySide6.QtCore import QEvent, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from core.state import prefs
from core.voice import devices
from ui.glass_menu import GlassMenu
from ui.symbols import set_symbol
from ui.theme import ACCENT, MIC_PILL_HEIGHT, TEXT, TEXT_DIM, TEXT_SECONDARY, WHITE, qcolor

_MIC_WIDTH = 30
_MENU_WIDTH = 18
_HOVER = qcolor(WHITE, 0.16)          # theme.SURFACE_HOVER
_BORDER = qcolor(WHITE, 0.10)         # theme.BORDER
_LISTENING = qcolor(ACCENT, 0.30)
_LISTENING_HOVER = qcolor(ACCENT, 0.42)
_SPINNER = qcolor(TEXT_SECONDARY)
_SPIN_MS = 16


class MicPill(QWidget):
    """Signals: mic_clicked() -- start or stop listening; device_picked() -- the input changed."""

    mic_clicked = Signal()
    device_picked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("micPill")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self._mic = QPushButton("●")
        self._mic.setObjectName("micBtn")
        self._mic.setFixedSize(_MIC_WIDTH, MIC_PILL_HEIGHT)
        self._mic.clicked.connect(self.mic_clicked)
        row.addWidget(self._mic)

        self._menu_btn = QPushButton("⌄")
        self._menu_btn.setObjectName("micMenuBtn")
        self._menu_btn.setFixedSize(_MENU_WIDTH, MIC_PILL_HEIGHT)
        self._menu_btn.setToolTip("Choose the microphone")
        self._menu_btn.clicked.connect(self._open_menu)
        set_symbol(self._menu_btn, "chevron.down", 7.5, TEXT_SECONDARY, bold=True)
        row.addWidget(self._menu_btn)

        for b in (self._mic, self._menu_btn):
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.installEventFilter(self)

        self._hover: QPushButton | None = None
        self._listening = False
        self._blocked = False
        self._busy = False
        self._angle = 0
        self._spin = QTimer(self)
        self._spin.setInterval(_SPIN_MS)
        self._spin.timeout.connect(self._advance)
        self.setFixedSize(_MIC_WIDTH + _MENU_WIDTH, MIC_PILL_HEIGHT)
        self.set_listening(False)

    # --- state ---
    def set_listening(self, on: bool) -> None:
        self._listening = on
        if self._busy and not on:
            return   # the spinner stays until the text is in
        set_symbol(self._mic, "stop.fill" if on else ("mic.slash" if self._blocked else "mic"),
                   9.5 if on else 11.5, TEXT if on else (TEXT_DIM if self._blocked else TEXT_SECONDARY))
        self._mic.setToolTip("Stop" if on else "Speak your message")
        self._menu_btn.setEnabled(not on)   # the input can't change mid-recording
        self.update()

    def set_blocked(self, blocked: bool, why: str = "") -> None:
        """Greyed (the daily limit): still clickable, so a click can say why."""
        self._blocked = blocked
        if not self._listening:
            self.set_listening(False)
        self._mic.setToolTip(why if blocked else "Speak your message")

    def set_busy(self, busy: bool) -> None:
        """A spinner in place of the mic while the last phrases are turned into text."""
        if busy == self._busy:
            return
        self._busy = busy
        if busy:
            self._mic.setIcon(QIcon())
            self._mic.setToolTip("Turning your words into text…")
            self._spin.start()
        else:
            self._spin.stop()
            self.set_listening(self._listening)
        self.update()

    def is_busy(self) -> bool:
        return self._busy

    def _advance(self) -> None:
        self._angle = (self._angle - 12) % 360
        self.update()

    def mic_anchor(self) -> QWidget:
        return self._mic

    # --- hover, tracked here: a menu takes the mouse, so the button never hears it leave ---
    def eventFilter(self, obj, event) -> bool:
        t = event.type()
        if t == QEvent.Type.Enter:
            self._hover = obj
            self.update()
        elif t == QEvent.Type.Leave and self._hover is obj:
            self._hover = None
            self.update()
        return False

    def _sync_hover(self) -> None:
        pos = self.mapFromGlobal(QCursor.pos())
        self._hover = next((b for b in (self._mic, self._menu_btn)
                            if b.isEnabled() and b.geometry().contains(pos)), None)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = r.height() / 2
        shape = QPainterPath()
        shape.addRoundedRect(r, radius, radius)
        p.setClipPath(shape)
        p.setPen(Qt.NoPen)
        mic_rect = QRectF(self._mic.geometry())
        menu_rect = QRectF(self._menu_btn.geometry())
        if self._listening:
            p.fillRect(mic_rect, _LISTENING_HOVER if self._hover is self._mic else _LISTENING)
        elif self._hover is self._mic:
            p.fillRect(mic_rect, _HOVER)
        if self._hover is self._menu_btn and self._menu_btn.isEnabled():
            p.fillRect(menu_rect, _HOVER)
        if self._busy:
            arc = QRectF(0, 0, 9, 9)
            arc.moveCenter(mic_rect.center())
            pen = QPen(_SPINNER, 1.6)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawArc(arc, self._angle * 16, 270 * 16)
        p.setClipping(False)
        p.setPen(QPen(_BORDER, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, radius, radius)

    # --- the input menu ---
    def _open_menu(self) -> None:
        current = prefs.mic_device()
        found = devices.inputs()
        if current not in {d for d, _ in found}:
            current = None   # the saved input is gone: the default is in use
        items = [("System Default", lambda: self._pick(None), True,
                  "checkmark" if current is None else None)]
        for dev_id, name in found:
            items.append((name, lambda d=dev_id: self._pick(d), True,
                          "checkmark" if dev_id == current else None))
        menu = GlassMenu(items)
        menu.destroyed.connect(lambda: QTimer.singleShot(0, self._sync_hover))
        menu.show_below(self)

    def _pick(self, device_id: str | None) -> None:
        prefs.set_mic_device(device_id)
        self.device_picked.emit()
