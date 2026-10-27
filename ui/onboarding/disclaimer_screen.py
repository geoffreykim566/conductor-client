"""Beta data-collection disclaimer; acknowledging it is required to continue."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout

from config import PRIVACY_URL
from ui.onboarding.centered_dialog import CenteredDialog
from ui.theme import ACCENT

# Keep in step with the website's privacy.html. A change to what users agree to
# bumps prefs.DISCLAIMER_VERSION so everyone sees it again.
_SENT = ("Your messages and usage", "Screenshots of Logic's windows only", "Logic's layout state")
_TERMS = (
    "Screenshots are never stored. Your data is never used for model training. "
    "It is only used to answer you and improve the app. "
    "Bug reports you send include your chat and logs."
)


class DisclaimerScreen(CenteredDialog):
    """Beta data-collection disclaimer. Acknowledging is required to continue."""

    finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(360, 370, parent)

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Conductor is in beta")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        items = "".join(f"<li>{s}</li>" for s in _SENT)
        sent = QLabel(
            "Conductor sends the following to our server:"
            f"<ul style='margin: 12px 0 0 -24px;'>{items}</ul>"
        )
        sent.setObjectName("subtitle")
        sent.setWordWrap(True)
        layout.addWidget(sent)
        layout.addSpacing(8)

        terms = QLabel(_TERMS)
        terms.setObjectName("subtitle")
        terms.setWordWrap(True)
        layout.addWidget(terms)

        links = QLabel(
            f"<a href='{PRIVACY_URL}' style='color: {ACCENT}; text-decoration: none;'>Privacy policy</a>"
        )
        links.setObjectName("subtitle")
        links.setAlignment(Qt.AlignCenter)
        links.setOpenExternalLinks(True)
        layout.addWidget(links)

        layout.addStretch()

        agree = QLabel("By continuing, you agree to this.")
        agree.setObjectName("subtitle")
        agree.setAlignment(Qt.AlignCenter)
        layout.addWidget(agree)

        btn = QPushButton("Continue")
        btn.setObjectName("primary")
        btn.clicked.connect(self._on_continue)
        layout.addWidget(btn)

    def _on_continue(self) -> None:
        self.finished.emit()
