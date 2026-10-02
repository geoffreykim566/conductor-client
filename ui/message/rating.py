"""Thumbs up/down row under a finished assistant bubble (mixin for MessageWidget)."""
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton

from ui.theme import ICON_BTN_SIZE


class RatingMixin:
    """Needs `self._role` and `self._outer` (the bubble's outer QVBoxLayout)."""

    def enable_rating(self, on_rate: Callable[[int], None], initial: int = 0) -> None:
        """Show thumbs up/down beneath a completed assistant message.

        on_rate is called with the new state whenever it changes: 1 (up), -1
        (down), or 0 (the user clicked the active button again, undoing the vote).
        `initial` restores a previously stored vote when reloading history.
        """
        if self._role != "assistant" or getattr(self, "_rate_row", None) is not None:
            return
        self._on_rate = on_rate
        self._rating = initial

        row = QHBoxLayout()
        row.setContentsMargins(6, 0, 0, 0)  # indent under the bubble's left edge
        row.setSpacing(4)
        self._up = QPushButton("Upvote ↑")
        self._down = QPushButton("Downvote ↓")
        for btn in (self._up, self._down):
            btn.setObjectName("rateBtn")
            btn.setFixedHeight(ICON_BTN_SIZE)
            btn.setCursor(Qt.PointingHandCursor)
        self._up.clicked.connect(lambda: self._rate(1))
        self._down.clicked.connect(lambda: self._rate(-1))
        row.addWidget(self._up)

        sep = QLabel("·")
        sep.setObjectName("remainingLabel")
        row.addWidget(sep)

        row.addWidget(self._down)
        row.addStretch()
        self._outer.addLayout(row)
        self._rate_row = row
        self._refresh_rating()

    def _rate(self, value: int) -> None:
        # Clicking the already-active button undoes the vote (back to 0).
        self._rating = 0 if self._rating == value else value
        self._on_rate(self._rating)
        self._refresh_rating()

    def _refresh_rating(self) -> None:
        """Highlight whichever button is active; both plain when there's no vote."""
        for btn, val in ((self._up, 1), (self._down, -1)):
            btn.setProperty("selected", self._rating == val)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
