"""WalkthroughCard: the step list and Run / Revert / Try again controls inside an assistant bubble."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.message.styles import (
    CARD_BUTTON_H,
    CARD_BUTTON_W,
    HINT_STYLE,
    STATUS_ERROR_STYLE,
    STATUS_INFO_STYLE,
    STEP_ACTIVE_STYLE,
    STEP_FAILED_STYLE,
    STEP_STYLE,
    system_font,
)
from ui.message.walkthrough_run import WalkthroughRunMixin
from ui.theme import MONO, TEXT_DIM


class WalkthroughCard(WalkthroughRunMixin, QWidget):
    """Card states: Ready (Run / ↵) -> Running (hands off; any real input stops)
    -> Done (Revert / ↵). `auto` skips Ready unless `destructive`. A failed or
    stopped run offers Try again (plus Revert when something already changed).
    """

    def __init__(self, steps: list, *, auto: bool = False, destructive: bool = False,
                 parent=None) -> None:
        super().__init__(parent)
        self._steps = steps
        self._active = False
        self._workers: list = []
        self._executor = None
        self._ledger: list = []   # every change still in effect, across Try agains
        self._resume = 0          # step a Try again starts from (ExecutorThread.resume_at)
        self._state = "ready"
        self._auto = bool(auto) and not destructive

        cl = QVBoxLayout(self)
        cl.setContentsMargins(0, 6, 0, 0)
        cl.setSpacing(2)

        self._step_labels: list[QLabel] = []
        for i, step in enumerate(steps):
            n = i + 1
            if "menu_path" in step:
                text = f"{n}. " + " → ".join(step["menu_path"])
            elif "shortcut" in step:
                text = f"{n}. ⌨  <b>{step['shortcut']}</b>"
            elif "click_value_of" in step:
                text = f"{n}. {step['click_value_of']}"
            elif "click_text" in step:
                val = step["click_text"]
                text = f"{n}. {val}" if isinstance(val, str) else f"{n}. (current selection)"
            elif "ax_open_plugin" in step:
                text = f"{n}. Open <b>{step['ax_open_plugin']}</b>"
            elif "choose" in step:
                v = step["choose"]
                text = (f"{n}. One step <b>{v}</b>" if v in ("larger", "smaller")
                        else f"{n}. Choose <b>{v}</b>")
            elif "ax_set_param" in step:
                p = step["ax_set_param"]
                text = f"{n}. {p.get('plugin', '')} · {p.get('param', '')} → <b>{p.get('value', '')}</b>"
            else:
                continue
            lbl = QLabel(text)
            lbl.setFont(system_font(11))
            lbl.setWordWrap(True)
            lbl.setStyleSheet(STEP_STYLE)
            cl.addWidget(lbl)
            self._step_labels.append(lbl)

        button = QPushButton("Run")
        button.setObjectName("primary")
        button.clicked.connect(self.enter)
        # Revert beside Try again, when a failed or stopped run changed something
        button2 = QPushButton("Revert")
        button2.setObjectName("secondary")
        button2.clicked.connect(self.revert)
        button2.hide()
        for b in (button, button2):
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedSize(CARD_BUTTON_W, CARD_BUTTON_H)
            b.setStyleSheet("padding: 0 12px;")   # the theme's 9px padding clips the label at this height
        row = QHBoxLayout()
        row.setContentsMargins(0, 4, 0, 0)
        row.setSpacing(8)
        row.addStretch(1)
        row.addWidget(button)
        row.addWidget(button2)
        row.addStretch(1)
        cl.addLayout(row)
        self._button = button
        self._button2 = button2

        hint = QLabel("Press ↵ to run")
        hint.setFont(system_font(10))
        hint.setStyleSheet(f"QLabel {{ font-family: {MONO}; color: {TEXT_DIM}; padding-left: 2px; margin-top: 4px; }}")
        cl.addWidget(hint)
        self._hint = hint

        end_hint = QLabel("Press any key to stop")
        end_hint.setFont(system_font(10))
        end_hint.setStyleSheet(HINT_STYLE)
        cl.addWidget(end_hint)
        self._end_hint = end_hint

        status = QLabel("")
        status.setFont(system_font(10))
        status.setWordWrap(True)
        status.hide()
        cl.addWidget(status)
        self._status = status

        self._highlight_step(0)
        if self._auto:
            self._hint.setText("Running automatically")
            QTimer.singleShot(0, self.enter)

    def _show_done(self, ledger: list, note: str = "Done") -> None:
        self._ledger = list(ledger or [])
        self._state = "done"
        self._end_hint.hide()
        self._button2.hide()
        self._status.setStyleSheet(STATUS_INFO_STYLE)
        self._status.setText(note)
        self._status.show()
        if self._ledger:
            self._button.setText("Revert")
            self._button.setEnabled(True)
            self._button.show()
            self._hint.setText("Press ↵ to revert")
            self._hint.show()
        else:
            self._button.hide()
            self._hint.hide()

    def _show_retry(self, note: str | None, *, error: bool = True) -> None:
        """A failed or stopped run: Try again (from `_resume`, re-reading
        Logic's state), plus Revert when something already changed."""
        self._state = "retry"
        self._end_hint.hide()
        if note is not None:
            self._status.setStyleSheet(STATUS_ERROR_STYLE if error else STATUS_INFO_STYLE)
            self._status.setText(note)
            self._status.show()
        self._button.setText("Try again")
        self._button.setEnabled(True)
        self._button.show()
        if self._ledger:
            self._button2.show()
        else:
            self._button2.hide()
        self._hint.setText("Press ↵ to try again")
        self._hint.show()

    def _highlight_step(self, idx: int) -> None:
        for i, lbl in enumerate(self._step_labels):
            lbl.setStyleSheet(STEP_ACTIVE_STYLE if i == idx else STEP_STYLE)

    def _mark_step_failed(self, idx: int) -> None:
        for i, lbl in enumerate(self._step_labels):
            lbl.setStyleSheet(STEP_FAILED_STYLE if i == idx else STEP_STYLE)

    def _show_permission_needed(self, msg: str | None = None) -> None:
        self._status.setText(
            msg or "Needs Accessibility permission — System Settings → Privacy & "
            "Security → Accessibility, then try again."
        )
        self._status.setStyleSheet(STATUS_ERROR_STYLE)
        self._status.show()
