"""Single chat message bubble (user or assistant)."""
import base64

from typing import Callable

from PySide6.QtCore import Qt, QTimer
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

from ui.theme import (
    ACCENT,
    ACCENT_TINT,
    BORDER,
    BUTTON_RADIUS,
    CHIP_RADIUS,
    DANGER,
    FONT_XS,
    ICON_BTN_SIZE,
    MONO,
    SCROLLBAR_GUTTER,
    SUCCESS,
    SUCCESS_TINT,
    SURFACE,
    SURFACE_RAISED,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
    TEXT_SECONDARY,
)

_STEP_STYLE = f"QLabel {{ color: {TEXT_MUTED}; padding-left: 2px; }}"
_STEP_ACTIVE_STYLE = f"QLabel {{ color: {TEXT}; font-weight: 600; padding-left: 2px; }}"
_STEP_FAILED_STYLE = f"QLabel {{ color: {DANGER}; font-weight: 600; padding-left: 2px; }}"
_HINT_STYLE = f"QLabel {{ color: {TEXT_DIM}; padding-left: 2px; }}"
_STATUS_ERROR_STYLE = f"QLabel {{ color: {DANGER}; padding-left: 2px; margin-top: 4px; }}"
_STATUS_INFO_STYLE = f"QLabel {{ color: {TEXT_SECONDARY}; padding-left: 2px; margin-top: 4px; }}"


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
                f"QLabel {{ background-color: {SURFACE}; color: {TEXT};"
                f" border: 1px solid {BORDER}; border-radius: {BUTTON_RADIUS}px;"
                f" font-family: {MONO}; font-size: {FONT_XS}px; padding: 6px 8px; }}"
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
        # Right margin trimmed by SCROLLBAR_GUTTER for user bubbles only --
        # they're right-aligned (bubble_row below), so chat_view.py's own
        # right-side gutter (reserved for the scrollbar) lands on top of
        # whatever's set here; assistant bubbles are left-aligned and don't
        # see that gutter at all (found live 2026-09-04: user bubbles sat
        # visibly further from the panel's right edge than assistant bubbles
        # sat from its left, once uncompensated).
        right_margin = 12 - SCROLLBAR_GUTTER if role == "user" else 12
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 3, right_margin, 3)
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
            thumb.setStyleSheet(f"border-radius: {BUTTON_RADIUS}px;")
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
        self._text_label.setText(f"<i style='color:{TEXT_MUTED}'>{text}</i>")
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
            btn.setFixedHeight(ICON_BTN_SIZE)
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

    # --- research confirm (2026-09-13) ---
    RESEARCH_PROMPT_TEXT = "Conductor wants to research the web - this can take a few minutes."

    def show_research_prompt(self, on_yes: Callable[[], None], on_no: Callable[[], None]) -> None:
        """Replace the bubble's status line with the research question and add
        a Yes/No row under the bubble, styled like the rating row (same
        #rateBtn pills, same height). Enter/Esc are handled by ChatWindow's
        app-level key filter and call the same callbacks as the buttons."""
        if self._role != "assistant" or getattr(self, "_research_row", None) is not None:
            return
        self.set_status_text(self.RESEARCH_PROMPT_TEXT)
        row = QHBoxLayout()
        row.setContentsMargins(6, 0, 0, 0)
        row.setSpacing(4)
        yes = QPushButton("Yes ↩")
        no = QPushButton("No esc")
        for btn in (yes, no):
            btn.setObjectName("rateBtn")
            btn.setFixedHeight(ICON_BTN_SIZE)
            btn.setCursor(Qt.PointingHandCursor)
        yes.clicked.connect(lambda: on_yes())
        no.clicked.connect(lambda: on_no())
        row.addWidget(yes)
        sep = QLabel("·")
        sep.setObjectName("remainingLabel")
        row.addWidget(sep)
        row.addWidget(no)
        row.addStretch()
        self._outer.addLayout(row)
        self._research_row = row
        self._research_widgets = (yes, sep, no)

    def hide_research_prompt(self) -> None:
        row = getattr(self, "_research_row", None)
        if row is None:
            return
        for w in self._research_widgets:
            row.removeWidget(w)
            w.deleteLater()
        self._outer.removeItem(row)
        self._research_row = None
        self._research_widgets = ()

    def mark_cancelled(self) -> None:
        """Esc mid-turn. A bubble with no real text yet just shows the
        status-style 'Cancelled'; one that already streamed part of an
        answer keeps it and gets the marker appended."""
        self.hide_research_prompt()
        if getattr(self, "_has_status", False) or not self._text:
            self.set_status_text("Cancelled")
        else:
            self.append_text("\n\n[cancelled]")

    # tier -> (label, background, foreground, hover explanation). Confidence
    # bands computed server-side (pipeline.py's _confidence_tier) off the same
    # deterministic trace data that used to drive a literal hedge sentence
    # forced onto the top of every "moderate" answer -- that text now lives in
    # this badge's tooltip instead (v3-log.md, 2026-09-04). "research" is
    # styled and ready but never sent yet -- no live web-research tool exists
    # in server-v3 today.
    _TIER_CHIP = {
        "strong": (
            "Confidence: Strong", ACCENT_TINT, ACCENT,
            "Confirmed against Conductor's verified Logic Pro knowledge base.",
        ),
        "moderate": (
            "Confidence: Moderate", SUCCESS_TINT, SUCCESS,
            "Confirmed against Conductor's verified Logic Pro knowledge base, "
            "but not as confidently as a strong match -- usually this means "
            "the model included its own knowledge alongside it that we "
            "couldn't completely verify.",
        ),
        "research": (
            "Research Verified", ACCENT_TINT, ACCENT,
            "Backed by a live web search for up-to-date information.",
        ),
        "generic": (
            "General Answer", SURFACE_RAISED, TEXT_SECONDARY,
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
        # Badges disabled 2026-09-12: the server-side tier is a trace rule that
        # fires on observational answers the KB lookup had nothing to do with
        # ("which tracks are muted" came back Moderate). The server now sends
        # "" as well, which the check below already ignores; this early return
        # covers the client-side timeout fallback and any old server. Chip
        # styling/tooltips kept for when the tier can tell an observation from
        # a recommendation.
        return
        if tier not in self._TIER_CHIP or self._role != "assistant" or getattr(self, "_tier_row", None) is not None:
            return
        label_text, bg, fg, tooltip = self._TIER_CHIP[tier]
        chip = _Chip(label_text, tooltip)
        chip.setStyleSheet(
            f"QLabel {{ background-color: {bg}; color: {fg}; border-radius: {CHIP_RADIUS}px;"
            f" font-family: {MONO}; font-size: {FONT_XS}px; font-weight: 600;"
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
            lbl = QLabel(
                f'<a href="{src["url"]}" style="color:{TEXT_SECONDARY};text-decoration:none;">{title}</a>'
            )
            lbl.setOpenExternalLinks(True)
            lbl.setFont(_system_font(10))
            lbl.setStyleSheet(
                f"QLabel {{ background-color: {SURFACE_RAISED}; color: {TEXT_SECONDARY};"
                f" border-radius: {CHIP_RADIUS}px; padding: 2px 8px; }}"
            )
            lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
            self._bubble_layout.addWidget(lbl)

    def setup_walkthrough(self, steps: list, *, auto: bool = False, destructive: bool = False) -> None:
        """Render a walkthrough/action card inside the bubble.

        Card states: Ready (Run / ↵) -> Running (hands off; any real input stops)
        -> Done (Revert / ↵ / Shift+Esc). `auto` skips Ready unless `destructive`.
        """
        if self._role != "assistant" or not steps:
            return
        self._wt_steps = steps
        self._wt_active = False
        self._wt_workers: list = []
        self._wt_executor = None
        self._wt_ledger: list = []
        self._wt_state = "ready"
        self._wt_auto = bool(auto) and not destructive

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
            elif "ax_open_plugin" in step:
                text = f"{n}.  Open <b>{step['ax_open_plugin']}</b>"
            elif "choose" in step:
                v = step["choose"]
                text = (f"{n}.  One step <b>{v}</b>" if v in ("larger", "smaller")
                        else f"{n}.  Choose <b>{v}</b>")
            elif "ax_set_param" in step:
                p = step["ax_set_param"]
                text = f"{n}.  {p.get('plugin', '')} · {p.get('param', '')} → <b>{p.get('value', '')}</b>"
            else:
                continue
            lbl = QLabel(text)
            lbl.setFont(_system_font(10))
            lbl.setWordWrap(True)
            lbl.setStyleSheet(_STEP_STYLE)
            cl.addWidget(lbl)
            self._wt_step_labels.append(lbl)

        button = QPushButton("Run")
        button.setObjectName("primary")
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedHeight(24)
        button.clicked.connect(self.wt_enter)
        cl.addWidget(button)
        self._wt_button = button

        hint = QLabel("Press ↵ to run")
        hint.setFont(_system_font(9))
        hint.setStyleSheet(f"QLabel {{ color: {TEXT_DIM}; padding-left: 2px; margin-top: 4px; }}")
        cl.addWidget(hint)
        self._wt_hint = hint

        end_hint = QLabel("Press any key to stop")
        end_hint.setFont(_system_font(9))
        end_hint.setStyleSheet(_HINT_STYLE)
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
        if self._wt_auto:
            self._wt_hint.setText("Running automatically")
            QTimer.singleShot(0, self.wt_enter)

    def wt_enter(self) -> None:
        """Enter / the card button. In Ready state it starts the run; in Done
        state it reverts. During a run it does nothing (any real input already
        stops the run via the interrupt tap)."""
        if not hasattr(self, "_wt_steps") or not hasattr(self, "_wt_card"):
            return
        if not self._wt_card.isVisible():
            return
        state = getattr(self, "_wt_state", "ready")
        if state == "done":
            self.wt_revert()
            return
        if state != "ready" or self._wt_active:
            return
        self._wt_active = True
        self._wt_state = "running"
        self._wt_hint.hide()
        self._wt_button.hide()
        self._wt_run_executor()

    def wt_shift_esc(self) -> None:
        """Shift+Esc: revert the last completed run (only meaningful in Done state)."""
        if getattr(self, "_wt_state", None) == "done":
            self.wt_revert()

    def wt_revert(self) -> None:
        from core.executor_thread import RevertThread
        if getattr(self, "_wt_state", None) != "done" or not getattr(self, "_wt_ledger", None):
            return
        self._wt_state = "reverting"
        self._wt_button.setEnabled(False)
        self._wt_status.setStyleSheet(_STATUS_INFO_STYLE)
        self._wt_status.setText("Reverting — hands off for a moment")
        self._wt_status.show()
        worker = RevertThread(self._wt_ledger, parent=self)
        worker.done.connect(self._wt_on_reverted)
        self._wt_workers.append(worker)
        worker.start()

    def _wt_on_reverted(self, results) -> None:
        self._wt_stop_threads()
        ok = all(r[1] for r in results) if results else False
        self._wt_ledger = []
        self._wt_state = "reverted"
        self._wt_button.hide()
        self._wt_hint.hide()
        self._wt_end_hint.hide()
        if ok:
            self._wt_status.setStyleSheet(_STATUS_INFO_STYLE)
            self._wt_status.setText("Reverted")
        else:
            failed = "; ".join(f"{r[0].get('label', '?')}: {r[2]}" for r in results if not r[1])
            self._wt_status.setStyleSheet(_STATUS_ERROR_STYLE)
            self._wt_status.setText(f"Couldn't revert everything — {failed}")
        self._wt_status.show()

    def _wt_show_done(self, ledger: list, note: str = "Done") -> None:
        self._wt_ledger = list(ledger or [])
        self._wt_state = "done"
        self._wt_end_hint.hide()
        self._wt_status.setStyleSheet(_STATUS_INFO_STYLE)
        self._wt_status.setText(note)
        self._wt_status.show()
        if self._wt_ledger:
            self._wt_button.setText("Revert")
            self._wt_button.setEnabled(True)
            self._wt_button.show()
            self._wt_hint.setText("↵ or Shift+Esc to revert")
            self._wt_hint.show()
        else:
            self._wt_button.hide()
            self._wt_hint.hide()

    def _wt_highlight_step(self, idx: int) -> None:
        for i, lbl in enumerate(self._wt_step_labels):
            lbl.setStyleSheet(_STEP_ACTIVE_STYLE if i == idx else _STEP_STYLE)

    def _wt_mark_step_failed(self, idx: int) -> None:
        for i, lbl in enumerate(self._wt_step_labels):
            lbl.setStyleSheet(_STEP_FAILED_STYLE if i == idx else _STEP_STYLE)

    def _wt_show_permission_needed(self, msg: str | None = None) -> None:
        self._wt_status.setText(
            msg or "Needs Accessibility permission — System Settings → Privacy & "
            "Security → Accessibility, then try again."
        )
        self._wt_status.setStyleSheet(_STATUS_ERROR_STYLE)
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

        self._wt_status.setStyleSheet(_STATUS_INFO_STYLE)
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

    def _wt_on_finished(self, ledger=None) -> None:
        print(f"[wt] executor finished; ledger={len(ledger or [])} entries")
        self._wt_teardown()
        if ledger:
            self._wt_show_done(ledger, "Done")
        else:
            self._wt_state = "finished"
            self._wt_card.hide()

    def _wt_on_failed(self, idx: int, msg: str) -> None:
        print(f"[wt] executor failed at step {idx}: {msg}")
        partial = list(getattr(self._wt_executor, "ledger", []) or [])
        self._wt_teardown()
        self._wt_mark_step_failed(idx)
        if partial:
            self._wt_show_done(partial, "Couldn't complete this step — earlier steps can be reverted.")
            self._wt_status.setStyleSheet(_STATUS_ERROR_STYLE)
        else:
            self._wt_state = "failed"
            self._wt_status.setStyleSheet(_STATUS_ERROR_STYLE)
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
