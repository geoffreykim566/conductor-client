"""Panel that lists all past chat sessions."""
from datetime import date, datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

MONO = '"Menlo", monospace'


def _format_date(session_id: str) -> str:
    if session_id == "legacy":
        return "Earlier session"
    try:
        dt = datetime.strptime(session_id, "%Y%m%d_%H%M%S")
        today = date.today()
        d = dt.date()
        time_str = dt.strftime("%-I:%M %p")
        if d == today:
            return f"Today  {time_str}"
        if (today - d).days == 1:
            return f"Yesterday  {time_str}"
        if (today - d).days < 7:
            return dt.strftime(f"%A  {time_str}")
        return dt.strftime(f"%b %-d  {time_str}")
    except ValueError:
        return session_id


class SessionListPanel(QWidget):
    """Overlay panel listing all sessions for the current song.

    Signals:
        session_selected(str)  — user clicked a session; emits its id
        closed()               — user dismissed the panel without selecting
    """

    session_selected = Signal(str)
    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── header ──────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("sessionHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 8, 12, 8)

        title = QLabel("PAST CHATS")
        title.setObjectName("sessionTitle")
        hl.addWidget(title)
        hl.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("headerBtn")
        close_btn.setFixedSize(20, 20)
        close_btn.clicked.connect(self.closed)
        hl.addWidget(close_btn)
        layout.addWidget(header)

        # ── scrollable list ──────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QScrollArea.NoFrame)

        self._container = QWidget()
        self._list_layout = QVBoxLayout(self._container)
        self._list_layout.setContentsMargins(0, 4, 0, 4)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll, 1)

        # ── empty state ──────────────────────────────────────────
        self._empty_placeholder = QWidget()
        _ep = QVBoxLayout(self._empty_placeholder)
        _ep.setContentsMargins(16, 0, 16, 0)
        _ep.addStretch(1)
        self._empty_label = QLabel("No past chats yet.")
        self._empty_label.setObjectName("sessionEmpty")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setWordWrap(True)
        _ep.addWidget(self._empty_label)
        _ep.addStretch(1)
        layout.addWidget(self._empty_placeholder, 1)

    def load(self, sessions: list[dict], current_id: str | None) -> None:
        """Populate the list. sessions is [{id, messages}, ...] oldest-first."""
        # Clear previous rows (keep the stretch at index 0)
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        visible_sessions = [s for s in sessions if s.get("messages")]
        self._empty_placeholder.setVisible(not visible_sessions)
        self._scroll.setVisible(bool(visible_sessions))

        for session in reversed(visible_sessions):
            sid = session["id"]
            messages = session.get("messages", [])
            first_user = next(
                (m["text"] for m in messages if m["role"] == "user"), "Empty"
            )
            preview = first_user[:72] + ("…" if len(first_user) > 72 else "")
            row = self._make_row(sid, preview, is_current=(sid == current_id))
            self._list_layout.insertWidget(
                self._list_layout.count() - 1, row
            )

    def _make_row(self, session_id: str, preview: str, is_current: bool) -> QFrame:
        row = QFrame()
        row.setObjectName("sessionRowActive" if is_current else "sessionRow")
        row.setCursor(Qt.PointingHandCursor)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        rl = QVBoxLayout(row)
        rl.setContentsMargins(16, 10, 16, 10)
        rl.setSpacing(3)

        date_lbl = QLabel(_format_date(session_id))
        date_lbl.setObjectName("sessionDate")
        rl.addWidget(date_lbl)

        prev_lbl = QLabel(preview)
        prev_lbl.setObjectName("sessionPreview")
        prev_lbl.setWordWrap(True)
        rl.addWidget(prev_lbl)

        row.mousePressEvent = lambda _e, sid=session_id: self.session_selected.emit(sid)
        return row
