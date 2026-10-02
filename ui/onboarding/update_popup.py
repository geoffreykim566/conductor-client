"""'Update available' prompt with a Download button."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout

from ui.onboarding.centered_dialog import CenteredDialog


class UpdatePopup(CenteredDialog):
    """Shown at launch when a newer version is available. Reappears every
    launch while an update is available -- Skip only dismisses this session,
    it doesn't persist a permanent opt-out (unlike FeedbackDialog's "Don't ask
    again": staying on an old version isn't a real preference to remember,
    just a launch someone hasn't updated yet)."""

    get_clicked = Signal()
    closed = Signal()

    def __init__(self, version: str, parent=None) -> None:
        super().__init__(360, 200, parent)

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Update available")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        body = QLabel(f"Conductor v{version} is available.")
        body.setObjectName("subtitle")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignCenter)
        layout.addWidget(body)

        layout.addStretch()

        get_btn = QPushButton("Download")
        get_btn.setObjectName("primary")
        get_btn.clicked.connect(self.get_clicked)
        layout.addWidget(get_btn)

        skip_btn = QPushButton("Skip")
        skip_btn.setObjectName("ghost")
        skip_btn.clicked.connect(self._finish)
        layout.addWidget(skip_btn)

    def _finish(self) -> None:
        self.closed.emit()
        self.close()
