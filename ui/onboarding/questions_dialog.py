"""One-time, skippable onboarding questions (experience, focus) sent to the server."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from core.net.account import put_me_async
from core.state.prefs import mark_questions_asked
from ui.onboarding.centered_dialog import CenteredDialog


class QuestionsDialog(CenteredDialog):
    """One-time onboarding questions, shown after the first message. Skippable."""

    closed = Signal()

    EXPERIENCE = [("Beginner", "beginner"), ("Intermediate", "intermediate"), ("Pro", "pro")]
    ROLES = [("Producer", "producer"), ("Mixer", "mixer"), ("Artist", "artist")]

    def __init__(self, parent=None) -> None:
        super().__init__(360, 320, parent)

        self._experience: str | None = None
        self._role: str | None = None
        self._exp_btns: list[QPushButton] = []
        self._role_btns: list[QPushButton] = []

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)

        title = QLabel("A couple of quick questions")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Helps us tailor Conductor. Optional.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(4)
        layout.addWidget(self._section("Your experience"))
        layout.addLayout(self._chip_row(self.EXPERIENCE, self._exp_btns, self._select_exp))
        layout.addWidget(self._section("Your focus"))
        layout.addLayout(self._chip_row(self.ROLES, self._role_btns, self._select_role))

        layout.addStretch()

        done_btn = QPushButton("Done")
        done_btn.setObjectName("primary")
        done_btn.clicked.connect(self._submit)
        layout.addWidget(done_btn)

        skip_row = QHBoxLayout()
        skip_row.addStretch()
        skip_btn = QPushButton("Skip")
        skip_btn.setObjectName("ghost")
        skip_btn.clicked.connect(self._skip)
        skip_row.addWidget(skip_btn)
        skip_row.addStretch()
        layout.addLayout(skip_row)

    def _section(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("subtitle")
        return label

    def _chip_row(self, options, store, on_select) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        for label, value in options:
            btn = QPushButton(label)
            btn.setObjectName("chip")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, v=value, b=btn: on_select(v, b, store))
            store.append(btn)
            row.addWidget(btn)
        return row

    def _highlight(self, chosen: QPushButton, group: list) -> None:
        for btn in group:
            btn.setProperty("selected", btn is chosen)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _select_exp(self, value: str, btn: QPushButton, store: list) -> None:
        self._experience = value
        self._highlight(btn, store)

    def _select_role(self, value: str, btn: QPushButton, store: list) -> None:
        self._role = value
        self._highlight(btn, store)

    def _submit(self) -> None:
        put_me_async(experience=self._experience, role=self._role)
        self._finish()

    def _skip(self) -> None:
        self._finish()

    def _finish(self) -> None:
        mark_questions_asked()
        self.closed.emit()
        self.close()
