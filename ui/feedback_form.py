"""Report Bug popup: pick Bug or Feedback, a title, an optional message, Submit."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core.net.feedback import FeedbackWorker
from ui.popup import Popup

BUG_NOTE = ("We'll attach the chat log, the action run log, Logic's window state, and your "
            "Logic and Conductor versions. We don't take a screenshot.")
FEEDBACK_NOTE = "Only your title and message are sent."
_SENT_CLOSE_MS = 1200
_QWIDGETSIZE_MAX = 16777215   # Qt's own max; PySide6 doesn't export the constant
# Sends still running after their form closed; held so the QThread isn't collected mid-run.
_in_flight: set[FeedbackWorker] = set()


class FeedbackForm(Popup):
    """`chat` and `server_history` are the open session, sent only with a bug or when the
    user ticks the context box on feedback. `kind` preselects a type (the usage prompt
    opens it on feedback)."""

    def __init__(self, chat: list[dict], server_history: list | None, kind: str | None = None) -> None:
        super().__init__("REPORT BUG", width=340)
        self._chat = chat
        self._server_history = server_history
        self._kind: str | None = None
        self._worker: FeedbackWorker | None = None

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        type_row = QHBoxLayout()
        type_row.setSpacing(6)
        self._type_btns: dict[str, QPushButton] = {}
        for key, label in (("bug", "Bug"), ("feedback", "Feedback")):
            btn = QPushButton(label)
            btn.setObjectName("chip")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._pick(k))
            type_row.addWidget(btn, 1)
            self._type_btns[key] = btn
        layout.addLayout(type_row)

        self._note = QLabel()
        self._note.setObjectName("subtitle")
        self._note.setWordWrap(True)
        self._note.hide()
        layout.addWidget(self._note)

        self._include = QCheckBox("Include the chat and logs")
        self._include.setToolTip("Attaches the chat log, the action run log, Logic's window state, "
                                 "and your Logic and Conductor versions, as a bug report does.")
        self._include.hide()
        layout.addWidget(self._include)

        self._title = QLineEdit()
        self._title.setPlaceholderText("Title")
        self._title.setMaxLength(200)
        self._title.textChanged.connect(self._refresh_submit)
        layout.addWidget(self._title)

        self._message = QTextEdit()
        self._message.setPlaceholderText("Message (optional)")
        self._message.setAcceptRichText(False)
        self._message.setTabChangesFocus(True)
        self._message.setFixedHeight(110)
        layout.addWidget(self._message)

        self._error = QLabel()
        self._error.setObjectName("error")
        self._error.setWordWrap(True)
        self._error.hide()
        layout.addWidget(self._error)

        self._submit = QPushButton("Submit")
        self._submit.setObjectName("primary")
        self._submit.clicked.connect(self._on_submit)
        layout.addWidget(self._submit)

        if kind:
            self._pick(kind)
        self._refresh_submit()

    def _pick(self, kind: str) -> None:
        self._kind = kind
        for key, btn in self._type_btns.items():
            btn.setProperty("selected", key == kind)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._note.setText(BUG_NOTE if kind == "bug" else FEEDBACK_NOTE)
        self._note.show()
        self._include.setVisible(kind == "feedback")
        self._refresh_submit()
        self._fit_height()
        self._title.setFocus()

    def _fit_height(self) -> None:
        """Grow or shrink for the note and checkbox, keeping the top edge in place."""
        # The panel is pinned to the old size (_sync_panel_size), which hides the new height.
        self._panel.setMinimumSize(0, 0)
        self._panel.setMaximumSize(_QWIDGETSIZE_MAX, _QWIDGETSIZE_MAX)
        layout = self._panel.layout()
        layout.activate()
        h = max(layout.totalHeightForWidth(self.width()), layout.totalMinimumSize().height())
        self.resize(self.width(), h)
        self._sync_panel_size()

    def _refresh_submit(self) -> None:
        busy = self._worker is not None
        self._submit.setEnabled(not busy and self._kind is not None and bool(self._title.text().strip()))

    def _on_submit(self) -> None:
        with_context = self._kind == "bug" or self._include.isChecked()
        self._error.hide()
        self._submit.setText("Sending…")
        self._worker = FeedbackWorker(
            self._kind, self._title.text().strip(), self._message.toPlainText().strip(),
            self._chat if with_context else None, self._server_history,
        )
        self._worker.sent.connect(self._on_sent)
        self._worker.failed.connect(self._on_failed)
        _in_flight.add(self._worker)
        self._worker.finished.connect(lambda w=self._worker: _in_flight.discard(w))
        self._refresh_submit()
        self._worker.start()

    def _on_sent(self) -> None:
        self._finish_worker()
        self._submit.setText("Sent. Thanks!")
        self._submit.setEnabled(False)
        QTimer.singleShot(_SENT_CLOSE_MS, self.close)

    def _on_failed(self, msg: str) -> None:
        self._finish_worker()
        self._submit.setText("Submit")
        self._error.setText(msg)
        self._error.show()
        self._refresh_submit()
        self._fit_height()

    def _finish_worker(self) -> None:
        self._worker = None
