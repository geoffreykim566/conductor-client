"""The first-run permission screen: one row per permission, asked one at a time."""
import objc
from AppKit import NSNormalWindowLevel, NSRunningApplication
from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.onboarding import permissions as perms
from ui.onboarding.centered_dialog import CenteredDialog
from ui.symbols import symbol_pixmap
from ui.theme import ACCENT

_POLL_MS = 1000
_ACTIVATE_IGNORING_OTHER_APPS = 2  # deprecated on 14+, still honoured (see core/automation/logic_focus.py)


class _Row(QWidget):
    """Title and detail on the left; Grant Access or a check on the right. After
    a click, a waiting note and the Open System Settings fallback show below."""

    def __init__(self, perm: perms.Permission, on_grant, on_open_settings, parent=None) -> None:
        super().__init__(parent)
        self.perm = perm
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(10)
        text = QVBoxLayout()
        text.setSpacing(2)
        title = QLabel(perm.title)
        title.setObjectName("rowTitle")
        title.setWordWrap(True)
        text.addWidget(title)
        detail = QLabel(perm.detail)
        detail.setObjectName("subtitle")
        detail.setWordWrap(True)
        text.addWidget(detail)
        row.addLayout(text, 1)

        self._btn = QPushButton("Grant Access")
        self._btn.setObjectName("chip")
        self._btn.clicked.connect(lambda: on_grant(self))
        row.addWidget(self._btn, 0, Qt.AlignVCenter)

        self._check = QLabel()
        pm = symbol_pixmap("checkmark.circle.fill", 18, ACCENT)
        if pm is not None:
            self._check.setPixmap(pm)
        else:
            self._check.setText("✓")
            self._check.setStyleSheet(f"color: {ACCENT}; font-size: 18px;")
        self._check.hide()
        row.addWidget(self._check, 0, Qt.AlignVCenter)
        outer.addLayout(row)

        self._waiting = QLabel(
            "Turn Conductor on, then come back here." if perm.live else
            "Turn Conductor on. macOS then asks to reopen Conductor to finish.")
        self._waiting.setObjectName("subtitle")
        self._waiting.setWordWrap(True)
        self._waiting.hide()
        outer.addWidget(self._waiting)

        self._fallback = QPushButton("Didn't see a popup? Open System Settings")
        self._fallback.setObjectName("ghost")
        self._fallback.clicked.connect(lambda: on_open_settings(self))
        self._fallback.hide()
        outer.addWidget(self._fallback, 0, Qt.AlignLeft)

    def set_state(self, granted: bool, active: bool, asked: bool) -> None:
        self._btn.setVisible(not granted)
        self._btn.setEnabled(active and not asked)
        self._check.setVisible(granted)
        self._waiting.setVisible(asked and not granted)
        self._fallback.setVisible(asked and not granted)


class PermissionsScreen(CenteredDialog):
    """Asks for each permission the way its old one-per-screen step did: the button
    calls the request (macOS's popup, which opens System Settings), and a 1 s poll
    ticks the row. Only the first missing row is live, so popups never stack."""

    finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(380, 400, parent)
        self._asked: set[str] = set()
        self._saved_level: int | None = None  # stay-on-top level while stepped back (_step_back)

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Permissions")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("Conductor needs two permissions to see and work in Logic Pro.")
        desc.setObjectName("subtitle")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)
        layout.addSpacing(4)

        self._rows = [_Row(p, self._on_grant, self._on_open_settings) for p in perms.setup_permissions()]
        for row in self._rows:
            layout.addWidget(row)

        layout.addStretch()

        skip_row = QHBoxLayout()
        skip_row.addStretch()
        skip_btn = QPushButton("Skip for now")
        skip_btn.setObjectName("ghost")
        skip_btn.clicked.connect(self._finish)
        skip_row.addWidget(skip_btn)
        skip_row.addStretch()
        layout.addLayout(skip_row)

        self._granted = [row.perm.check() for row in self._rows]
        self._apply()
        self._poll = QTimer(self)
        self._poll.setInterval(_POLL_MS)
        self._poll.timeout.connect(self._tick)
        self._poll.start()

    def _apply(self) -> None:
        active = perms.active_index(self._granted)
        for i, row in enumerate(self._rows):
            row.set_state(self._granted[i], i == active, row.perm.key in self._asked)

    def _tick(self) -> None:
        granted = [row.perm.check() for row in self._rows]
        newly_on = any(g and not was for g, was in zip(granted, self._granted))
        self._granted = granted
        self._apply()
        if all(granted):
            self._finish()
        elif newly_on:
            self.bring_to_front()

    def _on_grant(self, row: _Row) -> None:
        self._step_back()
        row.perm.request()
        self._asked.add(row.perm.key)
        self._apply()

    def _on_open_settings(self, row: _Row) -> None:
        self._step_back()
        QDesktopServices.openUrl(QUrl(row.perm.settings_url))

    def _ns_window(self):
        return objc.objc_object(c_void_p=int(self.winId())).window()

    def _step_back(self) -> None:
        """Drop below macOS's permission popup, which opens behind a stay-on-top
        window and can't be raised from here. bring_to_front() restores the level."""
        ns_window = self._ns_window()
        if self._saved_level is None:
            self._saved_level = ns_window.level()
        ns_window.setLevel_(NSNormalWindowLevel)
        ns_window.orderBack_(None)

    def bring_to_front(self) -> None:
        if self._saved_level is not None:
            self._ns_window().setLevel_(self._saved_level)
            self._saved_level = None
        # Qt.Tool windows hide while the app is inactive; activating the app shows this one again.
        NSRunningApplication.currentApplication().activateWithOptions_(_ACTIVATE_IGNORING_OTHER_APPS)
        self.show()
        self.raise_()
        self.activateWindow()

    def _finish(self) -> None:
        self._poll.stop()
        self.finished.emit()
