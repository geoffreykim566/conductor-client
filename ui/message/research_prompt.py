"""'Research the web?' Yes/No row under an assistant bubble (mixin for MessageWidget)."""
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton

from ui.theme import ICON_BTN_SIZE


class ResearchPromptMixin:
    """Needs `self._role`, `self._outer` and `set_status_text()` from MessageWidget."""

    RESEARCH_PROMPT_TEXT = "Conductor wants to research the web - this can take a few minutes."

    def show_research_prompt(self, on_yes: Callable[[], None], on_no: Callable[[], None]) -> None:
        """Replace the bubble's status line with the research question and add
        a Yes/No row under the bubble, styled like the rating row (same
        #rateBtn pills, same height). Enter/Esc are handled by ChatWindow's
        app-level key filter and call the same callbacks as the buttons."""
        if self._role != "assistant" or getattr(self, "_research_row", None) is not None:
            return
        self.set_status_text(self.RESEARCH_PROMPT_TEXT)
        row = QHBoxLayout()
        row.setContentsMargins(6, 0, 0, 0)
        row.setSpacing(4)
        yes = QPushButton("Yes ↩")
        no = QPushButton("No esc")
        for btn in (yes, no):
            btn.setObjectName("rateBtn")
            btn.setFixedHeight(ICON_BTN_SIZE)
            btn.setCursor(Qt.PointingHandCursor)
        yes.clicked.connect(lambda: on_yes())
        no.clicked.connect(lambda: on_no())
        row.addWidget(yes)
        sep = QLabel("·")
        sep.setObjectName("remainingLabel")
        row.addWidget(sep)
        row.addWidget(no)
        row.addStretch()
        self._outer.addLayout(row)
        self._research_row = row
        self._research_widgets = (yes, sep, no)

    def hide_research_prompt(self) -> None:
        row = getattr(self, "_research_row", None)
        if row is None:
            return
        for w in self._research_widgets:
            row.removeWidget(w)
            w.deleteLater()
        self._outer.removeItem(row)
        self._research_row = None
        self._research_widgets = ()
