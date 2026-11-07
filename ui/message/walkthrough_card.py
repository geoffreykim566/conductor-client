"""WalkthroughCard: the step list and Run / Revert / Try again controls inside an assistant bubble."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core import ax
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
from ui.onboarding.permissions import accessibility_name
from ui.theme import TEXT_DIM


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

        # One wire step can show as several numbered lines (a plug-in step is three keypresses);
        # _step_labels[i] holds wire step i's labels, so highlighting stays per wire step.
        self._step_labels: list[list[QLabel]] = []
        n = 0
        for step in steps:
            labels = []
            for line in self._step_lines(step):
                n += 1
                lbl = QLabel(f"{n}. {line}")
                lbl.setFont(system_font(11))
                lbl.setWordWrap(True)
                lbl.setStyleSheet(STEP_STYLE)
                cl.addWidget(lbl)
                labels.append(lbl)
            self._step_labels.append(labels)

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
        hint.setStyleSheet(f"QLabel {{ color: {TEXT_DIM}; padding-left: 2px; margin-top: 4px; }}")
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
        for i, labels in enumerate(self._step_labels):
            for lbl in labels:
                lbl.setStyleSheet(STEP_ACTIVE_STYLE if i == idx else STEP_STYLE)

    def _mark_step_failed(self, idx: int) -> None:
        for i, labels in enumerate(self._step_labels):
            for lbl in labels:
                lbl.setStyleSheet(STEP_FAILED_STYLE if i == idx else STEP_STYLE)

    @staticmethod
    def _step_lines(step: dict) -> list[str]:
        """What the user sees for one wire step, one line per thing they'd do by hand."""
        if "menu_path" in step:
            return [" → ".join(step["menu_path"])]
        if "shortcut" in step:
            return [f"⌨  <b>{step['shortcut']}</b>"]
        if "click_value_of" in step:
            return [step["click_value_of"]]
        if "click_text" in step:
            val = step["click_text"]
            return [val if isinstance(val, str) else "(current selection)"]
        if "ax_open_plugin" in step:
            # What the client actually presses (core/ax/plugins.py), so the user can repeat it.
            name = step["ax_open_plugin"]
            if ax.is_mastering(name):
                return [f"Open <b>{name}</b>"]
            return ["Press <b>⌃⌘P</b>", f"Type <b>{name}</b>", "Press <b>Return</b>"]
        if "choose" in step:
            v = step["choose"]
            return [f"One step <b>{v}</b>" if v in ("larger", "smaller") else f"Choose <b>{v}</b>"]
        if "context_menu" in step:
            what = f"“{step['target']}”" if step.get("target") else f"the {step.get('on') or 'region'}"
            return [f"Control-click {what} → " + " → ".join(step["context_menu"])]
        if "checks" in step:
            on = [k for k, v in step["checks"].items() if v]
            return [f"Tick <b>{', '.join(on)}</b>" + (" only" if len(on) < len(step["checks"]) else "")]
        if "ax_set_param" in step:
            p = step["ax_set_param"]
            v = str(p.get("value", ""))
            shown = f"by {v[3:]}" if v.lower().startswith("by:") else v
            return [f"{p.get('plugin', '')} · {p.get('param', '')} → <b>{shown}</b>"]
        return []

    def _show_permission_needed(self) -> None:
        self._status.setText(
            f"Needs {accessibility_name()} permission — System Settings → "
            f"Privacy & Security → {accessibility_name()}, then try again."
        )
        self._status.setStyleSheet(STATUS_ERROR_STYLE)
        self._status.show()
