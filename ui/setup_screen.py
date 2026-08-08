"""First-run setup screens and persisted local config (window size, onboarding state)."""
import json
import Quartz
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import APP_SUPPORT_DIR

_CONFIG_PATH = APP_SUPPORT_DIR / "config.json"

MONO = '"Menlo", monospace'

# Styling for these dialogs comes from the app-wide stylesheet (ui/style.py),
# applied once at the QApplication level in main.py.


def _read_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_config(data: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data, indent=2))


def get_saved_window_size() -> tuple[int, int] | None:
    data = _read_config()
    w, h = data.get("window_width"), data.get("window_height")
    if w and h:
        return (int(w), int(h))
    return None


def save_window_size(w: int, h: int) -> None:
    data = _read_config()
    data["window_width"] = w
    data["window_height"] = h
    _write_config(data)


def clear_window_size() -> None:
    data = _read_config()
    data.pop("window_width", None)
    data.pop("window_height", None)
    _write_config(data)


def get_saved_window_pos() -> tuple[int, int] | None:
    data = _read_config()
    x, y = data.get("window_x"), data.get("window_y")
    if x is not None and y is not None:
        return (int(x), int(y))
    return None


def save_window_pos(x: int, y: int) -> None:
    data = _read_config()
    data["window_x"] = x
    data["window_y"] = y
    _write_config(data)


def clear_window_pos() -> None:
    data = _read_config()
    data.pop("window_x", None)
    data.pop("window_y", None)
    _write_config(data)


def is_setup_complete() -> bool:
    """True once a free-tier user has finished onboarding (no key required)."""
    return bool(_read_config().get("setup_complete"))


def mark_setup_complete() -> None:
    data = _read_config()
    data["setup_complete"] = True
    _write_config(data)


def is_questions_asked() -> bool:
    """True once the post-first-message onboarding questions have been shown."""
    return bool(_read_config().get("questions_asked"))


def mark_questions_asked() -> None:
    data = _read_config()
    data["questions_asked"] = True
    _write_config(data)


def is_feedback_never_show() -> bool:
    return bool(_read_config().get("feedback_never_show"))


def mark_feedback_never_show() -> None:
    data = _read_config()
    data["feedback_never_show"] = True
    _write_config(data)


def reset_feedback_for_new_version() -> None:
    """Treat each app update as a fresh request for feedback."""
    from config import VERSION
    data = _read_config()
    if data.get("feedback_last_version") != VERSION:
        data.pop("feedback_never_show", None)
        data["feedback_last_version"] = VERSION
        _write_config(data)



def _centered_pos(widget: QWidget) -> tuple[int, int]:
    screen = QGuiApplication.primaryScreen().availableGeometry()
    return (
        screen.center().x() - widget.width() // 2,
        screen.center().y() - widget.height() // 2,
    )



def has_screen_recording_permission() -> bool:
    return bool(Quartz.CGPreflightScreenCaptureAccess())


def has_input_monitoring_permission() -> bool:
    return bool(Quartz.CGPreflightListenEventAccess())


class PermissionScreen(QWidget):
    """Step 1 of first-run: request Screen Recording access before anything else."""

    finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(360, 300)

        self._poll = QTimer(self)
        self._poll.setInterval(1000)
        self._poll.timeout.connect(self._check)

        root = QWidget(self)
        root.setObjectName("setupRoot")
        root.setGeometry(0, 0, 360, 300)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Screen Recording")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Conductor reads Logic Pro's windows to locate controls\n"
            "and run walkthroughs on screen."
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

        x, y = _centered_pos(self)
        self.move(x, y)

    def _on_grant(self) -> None:
        Quartz.CGRequestScreenCaptureAccess()
        self._btn.setEnabled(False)
        self._btn.setText("Waiting for approval…")
        self._status.setText("Toggle Conductor on in System Settings, then return here.")
        self._status.show()
        self._poll.start()

    def _check(self) -> None:
        if has_screen_recording_permission():
            self._poll.stop()
            self.finished.emit()


class InputMonitoringScreen(QWidget):
    """Requests Input Monitoring access, needed for the walkthrough kill switch (Shift+Esc)."""

    finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(360, 300)

        self._poll = QTimer(self)
        self._poll.setInterval(1000)
        self._poll.timeout.connect(self._check)

        root = QWidget(self)
        root.setObjectName("setupRoot")
        root.setGeometry(0, 0, 360, 300)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Input Monitoring")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Conductor listens for Shift+Esc so you can end a\n"
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

        x, y = _centered_pos(self)
        self.move(x, y)

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


class DisclaimerScreen(QWidget):
    """Beta data-collection disclaimer. Acknowledging is required to continue."""

    finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(360, 320)

        root = QWidget(self)
        root.setObjectName("setupRoot")
        root.setGeometry(0, 0, 360, 320)

        layout = QVBoxLayout(root)
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

        x, y = _centered_pos(self)
        self.move(x, y)

    def _on_continue(self) -> None:
        self.finished.emit()


class QuestionsDialog(QWidget):
    """One-time onboarding questions, shown after the first message. Skippable."""

    closed = Signal()

    EXPERIENCE = [("Beginner", "beginner"), ("Intermediate", "intermediate"), ("Pro", "pro")]
    ROLES = [("Producer", "producer"), ("Mixer", "mixer"), ("Artist", "artist")]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(360, 320)

        self._experience: str | None = None
        self._role: str | None = None
        self._exp_btns: list[QPushButton] = []
        self._role_btns: list[QPushButton] = []

        root = QWidget(self)
        root.setObjectName("setupRoot")
        root.setGeometry(0, 0, 360, 320)

        layout = QVBoxLayout(root)
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

        x, y = _centered_pos(self)
        self.move(x, y)

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
        from core.server_client import put_me_async
        put_me_async(experience=self._experience, role=self._role)
        self._finish()

    def _skip(self) -> None:
        self._finish()

    def _finish(self) -> None:
        mark_questions_asked()
        self.closed.emit()
        self.close()


class FeedbackDialog(QWidget):
    """Periodic feedback prompt shown after the user crosses a usage threshold."""

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(360, 240)

        root = QWidget(self)
        root.setObjectName("setupRoot")
        root.setGeometry(0, 0, 360, 240)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Give us feedback!")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        body = QLabel(
            "We'd love to hear your thoughts!\n"
            "The form takes less than a minute."
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

        x, y = _centered_pos(self)
        self.move(x, y)

    def _on_feedback(self) -> None:
        from config import FEEDBACK_FORM_URL
        QDesktopServices.openUrl(QUrl(FEEDBACK_FORM_URL))
        self._finish()

    def _on_never(self) -> None:
        mark_feedback_never_show()
        self._finish()

    def _finish(self) -> None:
        self.closed.emit()
        self.close()
