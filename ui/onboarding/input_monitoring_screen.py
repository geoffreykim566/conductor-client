"""Request Input Monitoring access (needed for the any-key walkthrough interrupt)."""
import Quartz
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ui.onboarding.centered_dialog import CenteredDialog
from ui.onboarding.permissions import has_input_monitoring_permission


class InputMonitoringScreen(CenteredDialog):
    """Requests Input Monitoring access, needed for the walkthrough kill switch (any key)."""

    finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(360, 300, parent)

        self._poll = QTimer(self)
        self._poll.setInterval(1000)
        self._poll.timeout.connect(self._check)

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Input Monitoring")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Conductor listens for any key, click, or scroll so you can end a\n"
            "walkthrough at any time, even while Logic Pro is focused."
        )
        desc.setObjectName("subtitle")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)

        layout.addStretch()

        self._status = QLabel("")
        self._status.setObjectName("subtitle")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setWordWrap(True)
        self._status.hide()
        layout.addWidget(self._status)

        self._btn = QPushButton("Grant Access")
        self._btn.setObjectName("primary")
        self._btn.clicked.connect(self._on_grant)
        layout.addWidget(self._btn)

        skip_row = QHBoxLayout()
        skip_row.addStretch()
        skip_btn = QPushButton("Skip for now")
        skip_btn.setObjectName("ghost")
        skip_btn.clicked.connect(self.finished.emit)
        skip_row.addWidget(skip_btn)
        skip_row.addStretch()
        layout.addLayout(skip_row)

    def _on_grant(self) -> None:
        Quartz.CGRequestListenEventAccess()
        self._btn.setEnabled(False)
        self._btn.setText("Waiting for approval…")
        self._status.setText("Toggle Conductor on in System Settings, then return here.")
        self._status.show()
        self._poll.start()

    def _check(self) -> None:
        if has_input_monitoring_permission():
            self._poll.stop()
            self.finished.emit()
