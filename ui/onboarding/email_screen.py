"""First setup screen: the waitlist email. A new Mac registers only with an approved email."""
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from config import WEBSITE_URL
from core.net.auth import RegistrationRefused, RegistrationThrottled, register
from ui.onboarding.centered_dialog import CenteredDialog
from ui.theme import ACCENT

_HELLO = "hello@askconductor.ai"


def refusal_text(reason: str) -> str:
    """What the screen says for each of the server's refusal codes."""
    return {
        "not_on_waitlist": "That email isn't on the waitlist. Check it for typos, "
                           "or sign up at askconductor.ai.",
        "not_approved": "You're on the waitlist, but not in yet. We'll email you when you are.",
        "install_limit": f"This email is already set up on the most Macs it can be. "
                         f"Email {_HELLO} if you need another.",
    }.get(reason, "Enter the email you signed up with.")


class _RegisterWorker(QThread):
    """register(email) off the UI thread; `result` is '' on success, else the message to show."""

    result = Signal(str)

    def __init__(self, email: str) -> None:
        super().__init__()
        self._email = email

    def run(self) -> None:
        try:
            register(self._email)
            self.result.emit("")
        except RegistrationRefused as e:
            self.result.emit(refusal_text(e.reason))
        except RegistrationThrottled:
            self.result.emit("Too many tries from this network. Try again in a while.")
        except Exception as e:
            print(f"[email_screen] register failed: {type(e).__name__}: {e}")
            self.result.emit("Couldn't reach Conductor. Check your connection and try again.")


class EmailScreen(CenteredDialog):
    """Asks for the waitlist email and registers this Mac with it."""

    finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(360, 300, parent)
        self._worker: _RegisterWorker | None = None

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(10)

        title = QLabel("Welcome to Conductor")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Enter the email you joined the waitlist with.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(6)

        self._input = QLineEdit()
        self._input.setPlaceholderText("you@example.com")
        self._input.returnPressed.connect(self._submit)
        self._input.textChanged.connect(lambda: self._error.hide())
        layout.addWidget(self._input)

        self._error = QLabel()
        self._error.setObjectName("error")
        self._error.setWordWrap(True)
        self._error.hide()
        layout.addWidget(self._error)

        layout.addStretch()

        self._btn = QPushButton("Continue")
        self._btn.setObjectName("primary")
        self._btn.clicked.connect(self._submit)
        layout.addWidget(self._btn)

        row = QHBoxLayout()
        join = QLabel(f"<a href='{WEBSITE_URL}' style='color: {ACCENT}; text-decoration: none;'>"
                      "Not on the waitlist? Join</a>")
        join.setObjectName("subtitle")
        join.setOpenExternalLinks(True)
        row.addWidget(join)
        row.addStretch()
        quit_btn = QPushButton("Quit")
        quit_btn.setObjectName("ghost")
        quit_btn.clicked.connect(QApplication.quit)
        row.addWidget(quit_btn)
        layout.addLayout(row)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.activateWindow()
        self._input.setFocus()

    def _submit(self) -> None:
        email = self._input.text().strip()
        if self._worker is not None:
            return
        if "@" not in email:
            self._show_error(refusal_text("email_required"))
            return
        self._btn.setEnabled(False)
        self._btn.setText("Checking…")
        self._worker = _RegisterWorker(email)
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, error: str) -> None:
        self._worker = None
        self._btn.setEnabled(True)
        self._btn.setText("Continue")
        if error:
            self._show_error(error)
        else:
            self.finished.emit()

    def _show_error(self, text: str) -> None:
        self._error.setText(text)
        self._error.show()
