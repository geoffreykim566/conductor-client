"""Beta data-collection disclaimer; acknowledging it is required to continue."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout

from ui.onboarding.centered_dialog import CenteredDialog


class DisclaimerScreen(CenteredDialog):
    """Beta data-collection disclaimer. Acknowledging is required to continue."""

    finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(360, 320, parent)

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Conductor is in beta")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        body = QLabel(
            "To improve Conductor, we collect the messages you send, the "
            "responses you get back, and basic usage while you use the app."
            "\n\nBy continuing, you agree to this."
        )
        body.setObjectName("subtitle")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignCenter)
        layout.addWidget(body)

        layout.addStretch()

        btn = QPushButton("Continue")
        btn.setObjectName("primary")
        btn.clicked.connect(self._on_continue)
        layout.addWidget(btn)

    def _on_continue(self) -> None:
        self.finished.emit()
