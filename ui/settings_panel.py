"""Settings overlay panel — shown when the user clicks the gear icon."""
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import song_history
from core.server_client import delete_me
from ui.setup_screen import (
    clear_window_size,
    get_saved_window_size,
    save_window_size,
)

_APP_DATA = Path.home() / "Library" / "Application Support" / "Conductor"

MONO = '"Menlo", monospace'


class SettingsPanel(QWidget):
    """Overlay panel for app settings.

    Signals:
        closed() — user dismissed without saving
        saved()  — user saved a new key
    """

    closed = Signal()
    history_cleared = Signal()
    reset_size_requested = Signal()
    size_locked = Signal(int, int)
    size_unlocked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("sessionHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 8, 12, 8)

        title = QLabel("SETTINGS")
        title.setObjectName("sessionTitle")
        hl.addWidget(title)
        hl.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("headerBtn")
        close_btn.setFixedSize(20, 20)
        close_btn.clicked.connect(self.closed)
        hl.addWidget(close_btn)
        layout.addWidget(header)

        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(16, 16, 16, 16)
        bl.setSpacing(10)

        # --- window size ---
        size_label = QLabel("WINDOW SIZE")
        size_label.setObjectName("sessionTitle")
        bl.addWidget(size_label)

        size_row = QHBoxLayout()
        size_row.setSpacing(6)
        self._size_display = QLabel("— × —")
        self._size_display.setObjectName("sessionDate")
        size_row.addWidget(self._size_display)
        size_row.addStretch()
        self._save_size_btn = QPushButton("Save")
        self._save_size_btn.setObjectName("primary")
        self._save_size_btn.setFixedWidth(64)
        self._save_size_btn.clicked.connect(self._on_save_size)
        size_row.addWidget(self._save_size_btn)
        self._red_size_btn = QPushButton("Reset to Default")
        self._red_size_btn.setObjectName("danger")
        self._red_size_btn.setFixedWidth(128)
        self._red_size_btn.clicked.connect(self._on_red_size)
        size_row.addWidget(self._red_size_btn)
        bl.addLayout(size_row)

        self._current_w = 0
        self._current_h = 0
        self._size_saved = False

        bl.addStretch()

        # --- danger zone ---
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #2a2a2c;")
        bl.addWidget(sep)

        danger_label = QLabel("DANGER ZONE")
        danger_label.setObjectName("sessionTitle")
        bl.addWidget(danger_label)

        # Delete history
        self._del_hist_btn = QPushButton("Delete Chat History")
        self._del_hist_btn.setObjectName("danger")
        self._del_hist_btn.clicked.connect(self._ask_delete_history)
        bl.addWidget(self._del_hist_btn)

        self._del_hist_confirm = self._make_confirm_row(
            "This cannot be undone.",
            self._confirm_delete_history,
            self._cancel_confirm,
        )
        self._del_hist_confirm.hide()
        bl.addWidget(self._del_hist_confirm)

        # Uninstall
        self._uninstall_btn = QPushButton("Uninstall Conductor")
        self._uninstall_btn.setObjectName("danger")
        self._uninstall_btn.clicked.connect(self._ask_uninstall)
        bl.addWidget(self._uninstall_btn)

        self._uninstall_confirm = self._make_confirm_row(
            "Deletes all data and quits. Drag Conductor.app to Trash to finish.",
            self._confirm_uninstall,
            self._cancel_confirm,
        )
        self._uninstall_confirm.hide()
        bl.addWidget(self._uninstall_confirm)

        layout.addWidget(body, 1)

    def refresh(self) -> None:
        saved = get_saved_window_size()
        self._apply_size_state(saved is not None)

    def set_window_size(self, w: int, h: int) -> None:
        self._current_w = w
        self._current_h = h
        self._size_display.setText(f"{w} × {h}")

    def _apply_size_state(self, saved: bool) -> None:
        self._size_saved = saved
        if saved:
            self._save_size_btn.setText("Saved")
            self._save_size_btn.setEnabled(False)
            self._red_size_btn.setText("Adjust")
            self._red_size_btn.setObjectName("secondary")
        else:
            self._save_size_btn.setText("Save")
            self._save_size_btn.setEnabled(True)
            self._red_size_btn.setText("Reset to Default")
            self._red_size_btn.setObjectName("danger")
        self._red_size_btn.style().unpolish(self._red_size_btn)
        self._red_size_btn.style().polish(self._red_size_btn)

    def _on_save_size(self) -> None:
        save_window_size(self._current_w, self._current_h)
        self._apply_size_state(True)
        self.size_locked.emit(self._current_w, self._current_h)

    def _on_red_size(self) -> None:
        clear_window_size()
        if self._size_saved:
            self._apply_size_state(False)
            self.size_unlocked.emit()
        else:
            self._apply_size_state(False)
            self.reset_size_requested.emit()

    # --- danger zone helpers ---
    def _make_confirm_row(self, warning: str, on_confirm, on_cancel) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(6)
        lbl = QLabel(warning)
        lbl.setObjectName("error")
        lbl.setWordWrap(True)
        vl.addWidget(lbl)
        row = QHBoxLayout()
        confirm_btn = QPushButton("Confirm")
        confirm_btn.setObjectName("danger")
        confirm_btn.clicked.connect(on_confirm)
        row.addWidget(confirm_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(on_cancel)
        row.addWidget(cancel_btn)
        vl.addLayout(row)
        return w

    def _ask_delete_history(self) -> None:
        self._del_hist_btn.hide()
        self._del_hist_confirm.show()

    def _ask_uninstall(self) -> None:
        self._uninstall_btn.hide()
        self._uninstall_confirm.show()

    def _cancel_confirm(self) -> None:
        self._del_hist_btn.show()
        self._del_hist_confirm.hide()
        self._uninstall_btn.show()
        self._uninstall_confirm.hide()

    def _confirm_delete_history(self) -> None:
        song_history.clear_all()
        self._cancel_confirm()
        self.history_cleared.emit()

    def _confirm_uninstall(self) -> None:
        delete_me()
        shutil.rmtree(_APP_DATA, ignore_errors=True)
        QApplication.quit()
