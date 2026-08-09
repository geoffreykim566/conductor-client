"""Settings popup — Danger Zone + window controls. Opened from the macOS menu bar."""
import shutil

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from config import APP_SUPPORT_DIR
from core import song_history
from core.server_client import delete_me
from ui.popup import Popup

_APP_DATA = APP_SUPPORT_DIR


class _ConfirmButton(QPushButton):
    """Arms (turns red, "Confirm?") on first click; only fires `confirmed` on
    a second click while armed. Auto-disarms after a few seconds so a stray
    later click can't land on an already-armed action."""

    confirmed = Signal()
    _ARM_TIMEOUT_MS = 3000

    def __init__(self, label: str) -> None:
        super().__init__(label)
        self._label = label
        self._armed = False
        self.setObjectName("secondary")
        self.clicked.connect(self._on_click)
        self._disarm_timer = QTimer(self)
        self._disarm_timer.setSingleShot(True)
        self._disarm_timer.timeout.connect(self._disarm)

    def _on_click(self) -> None:
        if self._armed:
            self._disarm()
            self.confirmed.emit()
        else:
            self._armed = True
            self.setObjectName("danger")
            self.setText("Confirm?")
            self._refresh_style()
            self._disarm_timer.start(self._ARM_TIMEOUT_MS)

    def _disarm(self) -> None:
        self._disarm_timer.stop()
        self._armed = False
        self.setObjectName("secondary")
        self.setText(self._label)
        self._refresh_style()

    def _refresh_style(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)


class _EditSizeButton(QPushButton):
    """Toggles between "Edit Size" and "Save" -- emits edit_requested on the
    first click, save_requested on the second (Save) click."""

    edit_requested = Signal()
    save_requested = Signal()

    def __init__(self) -> None:
        super().__init__("Edit Size")
        self.setObjectName("secondary")
        self._editing = False
        self.clicked.connect(self._on_click)

    def _on_click(self) -> None:
        self._editing = not self._editing
        self.setText("Save" if self._editing else "Edit Size")
        (self.edit_requested if self._editing else self.save_requested).emit()


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
        history_cleared()           — user confirmed clearing all chat history
        edit_size_requested()       — user clicked "Edit Size": show a resize border/grip
        save_size_requested()       — user clicked "Save": commit the current size
        reset_size_requested()      — user confirmed resetting size to default
        reset_position_requested()  — user confirmed resetting position to default
    """

    history_cleared = Signal()
    edit_size_requested = Signal()
    save_size_requested = Signal()
    reset_size_requested = Signal()
    reset_position_requested = Signal()

    def __init__(self) -> None:
        super().__init__("SETTINGS", width=300)
        self._confirm_popup: _ConfirmPopup | None = None

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        window_label = QLabel("WINDOW")
        window_label.setObjectName("sessionTitle")
        layout.addWidget(window_label)

        edit_size_btn = _EditSizeButton()
        edit_size_btn.edit_requested.connect(self.edit_size_requested)
        edit_size_btn.save_requested.connect(self.save_size_requested)
        layout.addWidget(edit_size_btn)

        reset_size_btn = _ConfirmButton("Reset Size")
        reset_size_btn.confirmed.connect(self.reset_size_requested)
        layout.addWidget(reset_size_btn)

        reset_pos_btn = _ConfirmButton("Reset Position")
        reset_pos_btn.confirmed.connect(self.reset_position_requested)
        layout.addWidget(reset_pos_btn)

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
