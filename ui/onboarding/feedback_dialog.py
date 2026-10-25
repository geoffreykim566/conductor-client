"""Feedback prompt shown when remaining free messages cross a threshold; opens the in-app form."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from core.state.prefs import mark_feedback_never_show
from ui.onboarding.centered_dialog import CenteredDialog


class FeedbackDialog(CenteredDialog):
    """Periodic feedback prompt shown after the user crosses a usage threshold."""

    closed = Signal()
    feedback_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(360, 240, parent)

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Give us feedback!")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        body = QLabel(
            "We'd love to hear your thoughts!\n"
            "It only takes a title."
        )
        body.setObjectName("subtitle")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignCenter)
        layout.addWidget(body)

        layout.addStretch()

        feedback_btn = QPushButton("Give Feedback")
        feedback_btn.setObjectName("primary")
        feedback_btn.clicked.connect(self._on_feedback)
        layout.addWidget(feedback_btn)

        bottom_row = QHBoxLayout()
        skip_btn = QPushButton("Skip")
        skip_btn.setObjectName("ghost")
        skip_btn.clicked.connect(self._finish)
        bottom_row.addWidget(skip_btn)
        bottom_row.addStretch()
        never_btn = QPushButton("Don't ask again")
        never_btn.setObjectName("ghost")
        never_btn.clicked.connect(self._on_never)
        bottom_row.addWidget(never_btn)
        layout.addLayout(bottom_row)

    def _on_feedback(self) -> None:
        self._finish()
        self.feedback_requested.emit()

    def _on_never(self) -> None:
        mark_feedback_never_show()
        self._finish()

    def _finish(self) -> None:
        self.closed.emit()
        self.close()
