"""Single chat message bubble (user or assistant)."""
import base64

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

def _system_font(size: int = 13) -> QFont:
    font = QApplication.font()
    font.setPointSize(size)
    return font


class _Chip(QLabel):
    """A QLabel with a custom hover popup instead of the native QToolTip.

    Native tooltips render *behind* this app's frameless, always-on-top main
    window on macOS (ChatWindow's Qt.WindowStaysOnTopHint) -- setToolTip()
    alone silently never showed anything (found live 2026-09-04: hovering
    changed the cursor but no tooltip ever appeared). This popup carries the
    same WindowStaysOnTopHint level itself so it isn't stuck behind its own
    parent window.
    """

    def __init__(self, text: str, hover_text: str) -> None:
        super().__init__(text)
        self._hover_text = hover_text
        self._popup: QWidget | None = None
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event) -> None:
        if self._popup is None:
            # The top-level widget itself must stay bare -- a translucent
            # top-level window never paints its own stylesheet background
            # (confirmed live: text rendered with no box at all). Same fix
            # ui/popup.py's Popup already uses: keep the window transparent,
            # put the actual background/border on a non-top-level child.
            popup = QWidget()
            popup.setWindowFlags(
                Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                | Qt.Tool | Qt.WindowDoesNotAcceptFocus
            )
            popup.setAttribute(Qt.WA_TranslucentBackground)
            layout = QVBoxLayout(popup)
            layout.setContentsMargins(0, 0, 0, 0)
            card = QLabel(self._hover_text)
            card.setWordWrap(True)
            card.setFixedWidth(220)
            card.setStyleSheet(
                "QLabel { background-color: #1c1c1e; color: #ebebf5;"
                " border: 1px solid #38383a; border-radius: 6px;"
                " font-family: 'Menlo', monospace; font-size: 10px; padding: 6px 8px; }"
            )
            layout.addWidget(card)
            self._popup = popup
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._popup.move(pos.x(), pos.y() + 4)
        self._popup.adjustSize()
        self._popup.show()
        self._popup.raise_()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self._popup is not None:
            self._popup.hide()
        super().leaveEvent(event)


class MessageWidget(QWidget):
    """A chat bubble. Use append_text() to grow streamed assistant messages."""

    def __init__(self, role: str, text: str = "", images_b64: list[str] | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self._role = role

        # Vertical stack so a rating row can sit *under* the bubble (like Claude),
        # outside the response itself.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 3, 12, 3)
        outer.setSpacing(3)
        self._outer = outer

        bubble = QFrame()
        bubble.setObjectName("userBubble" if role == "user" else "assistantBubble")
        bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 8, 12, 8)
        bubble_layout.setSpacing(6)
        self._bubble_layout = bubble_layout
        self._rating = 0

        for b64 in images_b64 or []:
            pix = QPixmap()
            pix.loadFromData(base64.b64decode(b64), "PNG")
            thumb = QLabel()
            thumb.setPixmap(pix.scaledToWidth(240, Qt.SmoothTransformation))
            thumb.setStyleSheet("border-radius: 6px;")
            bubble_layout.addWidget(thumb)

        self._text = text
        self._text_label = QLabel(text)
        self._text_label.setFont(_system_font(13))
        self._text_label.setWordWrap(True)
        self._text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if role == "assistant":
            self._text_label.setMinimumWidth(220)
        self._text_label.setMaximumWidth(270)
        self._text_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        bubble_layout.addWidget(self._text_label)

        # Bubble row: align user right, assistant left.
        bubble_row = QHBoxLayout()
        bubble_row.setContentsMargins(0, 0, 0, 0)
        if role == "user":
            bubble_row.addStretch()
            bubble_row.addWidget(bubble)
        else:
            bubble_row.addWidget(bubble)
            bubble_row.addStretch()
        outer.addLayout(bubble_row)

    def set_status_text(self, text: str) -> None:
        """Show a dim italic placeholder during research. Cleared on first real chunk."""
        self._has_status = True
        self._text_label.setText(f"<i style='color:#636366'>{text}</i>")
        self._text_label.setTextFormat(Qt.RichText)

    def append_text(self, chunk: str) -> None:
        if getattr(self, "_has_status", False):
            self._has_status = False
            self._text = ""
            self._text_label.setTextFormat(Qt.AutoText)
        self._text += chunk
        self._text_label.setText(self._text)

    def enable_rating(self, on_rate: Callable[[int], None], initial: int = 0) -> None:
        """Show thumbs up/down beneath a completed assistant message.

        on_rate is called with the new state whenever it changes: 1 (up), -1
        (down), or 0 (the user clicked the active button again, undoing the vote).
        `initial` restores a previously stored vote when reloading history.
        """
        if self._role != "assistant" or getattr(self, "_rate_row", None) is not None:
            return
        self._on_rate = on_rate
        self._rating = initial

        row = QHBoxLayout()
        row.setContentsMargins(6, 0, 0, 0)  # indent under the bubble's left edge
        row.setSpacing(4)
        self._up = QPushButton("Upvote ↑")
        self._down = QPushButton("Downvote ↓")
        for btn in (self._up, self._down):
            btn.setObjectName("rateBtn")
            btn.setFixedHeight(20)
            btn.setCursor(Qt.PointingHandCursor)
        self._up.clicked.connect(lambda: self._rate(1))
        self._down.clicked.connect(lambda: self._rate(-1))
        row.addWidget(self._up)

        sep = QLabel("·")
        sep.setObjectName("remainingLabel")
        row.addWidget(sep)

        row.addWidget(self._down)
        row.addStretch()
        self._outer.addLayout(row)
        self._rate_row = row
        self._refresh_rating()

    # tier -> (label, background, foreground, hover explanation). Confidence
    # bands computed server-side (pipeline.py's _confidence_tier) off the same
    # deterministic trace data that used to drive a literal hedge sentence
    # forced onto the top of every "moderate" answer -- that text now lives in
    # this badge's tooltip instead (v3-log.md, 2026-09-04). "research" is
    # styled and ready but never sent yet -- no live web-research tool exists
    # in server-v3 today.
    _TIER_CHIP = {
        "strong": (
            "Confidence: Strong", "#1c2a3a", "#0a84ff",
            "Confirmed against Conductor's verified Logic Pro knowledge base.",
        ),
        "moderate": (
            "Confidence: Moderate", "#1c3a2a", "#30d158",
            "Confirmed against Conductor's verified Logic Pro knowledge base, "
            "but not as confidently as a strong match -- usually this means "
            "the model included its own knowledge alongside it that we "
            "couldn't completely verify.",
        ),
        "research": (
            "Research Verified", "#1c2a3a", "#0a84ff",
            "Backed by a live web search for up-to-date information.",
        ),
        "generic": (
            "General Answer", "#2c2c2e", "#8e8e93",
            "The knowledge base didn't have anything for this -- treat this "
            "as general guidance from the model's own knowledge, not a "
            "confirmed answer.",
        ),
    }

    def set_source_tier(self, tier: str) -> None:
        """Add a small confidence badge below the bubble (hover for what it means).

        Deliberately outside the bubble, not inline in the response text --
        the old design forced a full hedge sentence at the top of every
        moderate-confidence answer, which read as noisy on turns where it
        fired often. The badge carries the same signal passively instead.
        """
        if tier not in self._TIER_CHIP or self._role != "assistant" or getattr(self, "_tier_row", None) is not None:
            return
        label_text, bg, fg, tooltip = self._TIER_CHIP[tier]
        chip = _Chip(label_text, tooltip)
        chip.setStyleSheet(
            f"QLabel {{ background-color: {bg}; color: {fg}; border-radius: 4px;"
            f" font-family: 'Menlo', monospace; font-size: 10px; font-weight: 600;"
            f" padding: 1px 6px; }}"
        )
        chip.setFixedHeight(18)
        chip.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

        row = QHBoxLayout()
        row.setContentsMargins(6, 0, 0, 0)  # indent under the bubble's left edge
        row.addWidget(chip)
        row.addStretch()
        self._outer.addLayout(row)
        self._tier_row = row

    def set_sources(self, sources: list) -> None:
        """Add source chips inside the bubble, stacked vertically (research turns only)."""
        url_sources = [s for s in sources if s.get("url")]
        if not url_sources or self._role != "assistant":
            return
        for src in url_sources[:3]:
            title = src.get("title") or src.get("url", "")
            if len(title) > 44:
                title = title[:42] + "…"
            lbl = QLabel(f'<a href="{src["url"]}" style="color:#8E8E93;text-decoration:none;">{title}</a>')
            lbl.setOpenExternalLinks(True)
            lbl.setFont(_system_font(10))
            lbl.setStyleSheet(
                "QLabel { background-color: #2C2C2E; color: #8E8E93; border-radius: 4px;"
                " padding: 2px 8px; }"
            )
            lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
            self._bubble_layout.addWidget(lbl)

    def setup_walkthrough(self, steps: list) -> None:
        """Render a walkthrough step-list card inside the bubble. Press Enter to run."""
        if self._role != "assistant" or not steps:
            return
        self._wt_steps = steps
        self._wt_active = False
        self._wt_workers: list = []
        self._wt_executor = None

        card = QWidget()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 6, 0, 0)
        cl.setSpacing(2)

        self._wt_step_labels: list[QLabel] = []
        for i, step in enumerate(steps):
            n = i + 1
            if "menu_path" in step:
                text = f"{n}.  " + " → ".join(step["menu_path"])
            elif "shortcut" in step:
                text = f"{n}.  ⌨  <b>{step['shortcut']}</b>"
            elif "click_value_of" in step:
                text = f"{n}.  {step['click_value_of']}"
            elif "click_text" in step:
                val = step["click_text"]
                text = f"{n}.  {val}" if isinstance(val, str) else f"{n}.  (current selection)"
            else:
                continue
            lbl = QLabel(text)
            lbl.setFont(_system_font(10))
            lbl.setWordWrap(True)
            lbl.setStyleSheet("QLabel { color: #636366; padding-left: 2px; }")
            cl.addWidget(lbl)
            self._wt_step_labels.append(lbl)

        hint = QLabel("Press ↵ to run")
        hint.setFont(_system_font(9))
        hint.setStyleSheet("QLabel { color: #48484a; padding-left: 2px; margin-top: 4px; }")
        cl.addWidget(hint)
        self._wt_hint = hint

        end_hint = QLabel("Press any key to stop")
        end_hint.setFont(_system_font(9))
        end_hint.setStyleSheet("QLabel { color: #48484a; padding-left: 2px; }")
        cl.addWidget(end_hint)
        self._wt_end_hint = end_hint

        status = QLabel("")
        status.setFont(_system_font(9))
        status.setWordWrap(True)
        status.hide()
        cl.addWidget(status)
        self._wt_status = status

        self._wt_card = card
        self._bubble_layout.addWidget(card)
        self._wt_highlight_step(0)

    def wt_enter(self) -> None:
        """Called when Enter pressed with empty input while this walkthrough is active.

        Enter is a one-time start signal only — once running, the executor thread
        drives everything (which step is current, whether it succeeded, when it ends).
        """
        if not hasattr(self, "_wt_steps") or not hasattr(self, "_wt_card"):
            return
        if not self._wt_card.isVisible():
            return
        if self._wt_active:
            return
        self._wt_active = True
        self._wt_hint.hide()
        self._wt_run_executor()

    def _wt_highlight_step(self, idx: int) -> None:
        for i, lbl in enumerate(self._wt_step_labels):
            if i == idx:
                lbl.setStyleSheet("QLabel { color: #ebebf5; font-weight: 600; padding-left: 2px; }")
            else:
                lbl.setStyleSheet("QLabel { color: #636366; padding-left: 2px; }")

    def _wt_mark_step_failed(self, idx: int) -> None:
        for i, lbl in enumerate(self._wt_step_labels):
            if i == idx:
                lbl.setStyleSheet("QLabel { color: #ff453a; font-weight: 600; padding-left: 2px; }")
            else:
                lbl.setStyleSheet("QLabel { color: #636366; padding-left: 2px; }")

    def _wt_show_permission_needed(self, msg: str | None = None) -> None:
        self._wt_status.setText(
            msg or "Needs Accessibility permission — System Settings → Privacy & "
            "Security → Accessibility, then try again."
        )
        self._wt_status.setStyleSheet("QLabel { color: #ff453a; padding-left: 2px; margin-top: 4px; }")
        self._wt_status.show()

    def _wt_run_executor(self) -> None:
        import threading

        from core.executor import check_event_permission, wire_to_steps
        from core.executor_thread import ExecutorThread
        from core.interrupt_tap import WalkthroughInterruptTap

        if not check_event_permission():
            self._wt_show_permission_needed()
            self._wt_active = False
            return
        translated = wire_to_steps(self._wt_steps)
        if not translated:
            self._wt_show_permission_needed()
            self._wt_active = False
            return

        interrupt_tap = WalkthroughInterruptTap(parent=self)
        if not interrupt_tap.arm():
            self._wt_show_permission_needed(
                "Needs Input Monitoring permission — System Settings → Privacy & "
                "Security → Input Monitoring, then try again."
            )
            self._wt_active = False
            return

        self._wt_status.setStyleSheet("QLabel { color: #8e8e93; padding-left: 2px; margin-top: 4px; }")
        self._wt_status.setText("Running — hands off for a moment")
        self._wt_status.show()

        stop_event = threading.Event()
        executor = ExecutorThread(translated, stop_event=stop_event, parent=self)
        executor.step_started.connect(self._wt_on_step_started)
        executor.finished.connect(self._wt_on_finished)
        executor.failed.connect(self._wt_on_failed)
        self._wt_executor = executor
        self._wt_workers.append(executor)  # keep-alive: stop() doesn't exit the
        # thread immediately, so the last strong ref can't drop until it does

        # Instant + non-blocking: unblocks the in-flight action within about
        # one keystroke. The UI teardown is queued rather than run inline —
        # _wt_end() -> _wt_teardown() blocks up to 2s waiting for the thread
        # to exit, and doing that synchronously inside the tap callback risks
        # macOS disabling the tap for taking too long to return.
        interrupt_tap.triggered.connect(stop_event.set)
        interrupt_tap.triggered.connect(self._wt_end, Qt.ConnectionType.QueuedConnection)
        self._wt_interrupt_tap = interrupt_tap

        executor.start()

    def _wt_on_step_started(self, idx: int) -> None:
        print(f"[wt] executor step_started idx={idx}")
        self._wt_highlight_step(idx)

    def _wt_on_finished(self) -> None:
        print("[wt] executor finished")
        self._wt_teardown()
        self._wt_card.hide()

    def _wt_on_failed(self, idx: int, msg: str) -> None:
        print(f"[wt] executor failed at step {idx}: {msg}")
        self._wt_teardown()
        self._wt_mark_step_failed(idx)
        self._wt_status.setStyleSheet("QLabel { color: #ff453a; padding-left: 2px; margin-top: 4px; }")
        self._wt_status.setText("Couldn't complete this step automatically — do it manually.")
        self._wt_status.show()
        # Card stays visible (not hidden) so the step list remains as a manual guide.

    def _wt_stop_threads(self) -> None:
        """Synchronously stop and wait for any running walkthrough thread.

        Qt6 aborts the whole process if a QThread is destroyed while still
        running (QThread::~QThread() calls qFatal(), not just a warning) —
        confirmed via multiple recurring "Python crashed" reports, all with
        this exact fatal-abort signature. .stop() alone only sets a flag and
        returns immediately, so anything that can tear down this widget (or
        the app) must wait for the thread to actually exit first.
        """
        for w in getattr(self, "_wt_workers", []):
            if w.isRunning():
                if hasattr(w, "stop"):
                    w.stop()
                w.wait(2000)
        self._wt_workers = []

    def _wt_teardown(self) -> None:
        self._wt_stop_threads()
        self._wt_executor = None
        self._wt_active = False
        if getattr(self, "_wt_interrupt_tap", None) is not None:
            self._wt_interrupt_tap.disarm()
            self._wt_interrupt_tap = None

    def _wt_end(self) -> None:
        """External/interrupt stop (any real key/click/scroll, idle) — tears down and hides the card."""
        self._wt_teardown()
        try:
            from ui.overlay_window import instance as _overlay
            _overlay().dismiss()
        except Exception:
            pass
        self._wt_card.hide()

    def force_end_walkthrough(self) -> None:
        """External safety hook: stop any active walkthrough before this
        widget (or the app) is torn down. Safe to call on any MessageWidget,
        even one that never set up a walkthrough card — call this before
        deleting/clearing message widgets or on app quit.
        """
        if not getattr(self, "_wt_active", False):
            return
        self._wt_active = False
        self._wt_end()

    def _rate(self, value: int) -> None:
        # Clicking the already-active button undoes the vote (back to 0).
        self._rating = 0 if self._rating == value else value
        self._on_rate(self._rating)
        self._refresh_rating()

    def _refresh_rating(self) -> None:
        """Highlight whichever button is active; both plain when there's no vote."""
        for btn, val in ((self._up, 1), (self._down, -1)):
            btn.setProperty("selected", self._rating == val)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
