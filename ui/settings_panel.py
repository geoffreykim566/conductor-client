"""Settings popup — Danger Zone + window reset. Opened from the macOS menu bar."""
import shutil

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from config import APP_SUPPORT_DIR
from core import song_history
from core.server_client import delete_me
from ui.popup import Popup

_APP_DATA = APP_SUPPORT_DIR


class _ConfirmPopup(Popup):
    """Small centered confirm/cancel popup, used for the two Danger Zone actions."""

    def __init__(self, warning: str, on_confirm) -> None:
        super().__init__("CONFIRM", width=280)
        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        lbl = QLabel(warning)
        lbl.setObjectName("error")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        row = QHBoxLayout()
        confirm_btn = QPushButton("Confirm")
        confirm_btn.setObjectName("danger")
        confirm_btn.clicked.connect(lambda: (on_confirm(), self.close()))
        row.addWidget(confirm_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.close)
        row.addWidget(cancel_btn)
        layout.addLayout(row)


class SettingsPanel(Popup):
    """Settings popup.

    Signals:
        history_cleared()          — user confirmed clearing all chat history
        reset_window_requested()   — user asked to reset window size/position to default
    """

    history_cleared = Signal()
    reset_window_requested = Signal()

    def __init__(self) -> None:
        super().__init__("SETTINGS", width=300)
        self._confirm_popup: _ConfirmPopup | None = None

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        window_label = QLabel("WINDOW")
        window_label.setObjectName("sessionTitle")
        layout.addWidget(window_label)

        reset_btn = QPushButton("Reset Window")
        reset_btn.setObjectName("secondary")
        reset_btn.clicked.connect(self.reset_window_requested)
        layout.addWidget(reset_btn)

        layout.addSpacing(4)
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #2a2a2c;")
        layout.addWidget(sep)

        danger_label = QLabel("DANGER ZONE")
        danger_label.setObjectName("sessionTitle")
        layout.addWidget(danger_label)

        del_hist_btn = QPushButton("Delete Chat History")
        del_hist_btn.setObjectName("danger")
        del_hist_btn.clicked.connect(self._ask_delete_history)
        layout.addWidget(del_hist_btn)

        uninstall_btn = QPushButton("Uninstall Conductor")
        uninstall_btn.setObjectName("danger")
        uninstall_btn.clicked.connect(self._ask_uninstall)
        layout.addWidget(uninstall_btn)

    def _ask_delete_history(self) -> None:
        self._confirm_popup = _ConfirmPopup(
            "Delete all chat history. This cannot be undone.",
            self._confirm_delete_history,
        )
        self._confirm_popup.center_on_screen()
        self._confirm_popup.show()

    def _confirm_delete_history(self) -> None:
        song_history.clear_all()
        self.history_cleared.emit()

    def _ask_uninstall(self) -> None:
        self._confirm_popup = _ConfirmPopup(
            "Deletes all data and quits. Drag Conductor.app to Trash to finish.",
            self._confirm_uninstall,
        )
        self._confirm_popup.center_on_screen()
        self._confirm_popup.show()

    def _confirm_uninstall(self) -> None:
        delete_me()
        shutil.rmtree(_APP_DATA, ignore_errors=True)
        QApplication.quit()
