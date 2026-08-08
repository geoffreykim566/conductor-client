"""Single chat message bubble (user or assistant)."""
import base64
import io
import math

from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
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

class _LocateWorker(QThread):
    """Background thread: runs the OCR locate pipeline and emits the result."""
    found = Signal(object)

    def __init__(self, element: str, parent=None) -> None:
        super().__init__(parent)
        self._element = element

    def run(self) -> None:
        print(f"[locate_worker] target={self._element!r}")
        try:
            from core.locate import resolve
            from core.server_client import fetch_control_map
            raw_map = fetch_control_map()
            result = resolve(self._element, element=self._element, raw_map=raw_map)
        except Exception as exc:
            print(f"[locate_worker] exception: {exc}")
            result = {"box": None, "img": None, "plugin": None,
                      "size": None, "word_count": 0, "error": str(exc)}
        box = result.get("box")
        deny = result.get("deny_reason", "")
        print(f"[locate_worker] result: box={'found' if box else 'None'}  deny={deny!r}  words={result.get('word_count')}  plugin={result.get('plugin')!r}")
        self.found.emit(result)


def _system_font(size: int = 13) -> QFont:
    font = QApplication.font()
    font.setPointSize(size)
    return font


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

    def set_source_tier(self, tier: str) -> None:
        """Add a small chip inside the bubble for notable source tiers."""
        _CHIP = {
            "expert-reviewed":   ("Expert",     "#1c3a2a", "#30d158"),
            "community-verified": ("Community",  "#1c2a3a", "#0a84ff"),
            "confirmed-research": ("Researched", "#2a2a1c", "#ffd60a"),
        }
        if tier not in _CHIP or self._role != "assistant":
            return
        label_text, bg, fg = _CHIP[tier]
        chip = QLabel(label_text)
        chip.setStyleSheet(
            f"QLabel {{ background-color: {bg}; color: {fg}; border-radius: 4px;"
            f" font-family: 'Menlo', monospace; font-size: 10px; font-weight: 600;"
            f" padding: 1px 6px; }}"
        )
        chip.setFixedHeight(18)
        chip.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._bubble_layout.addWidget(chip)

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

    def setup_locate(self, element: str) -> None:
        """Run locate in the background; show 'Show me on screen' only if found."""
        if self._role != "assistant" or not element:
            return
        self._locate_element = element
        self._locate_result_cache: dict | None = None
        self._locate_container: QWidget | None = None
        self._show_me_btn: QPushButton | None = None
        self._locate_worker = _LocateWorker(element, parent=self)
        self._locate_worker.found.connect(self._on_locate_result)
        self._locate_worker.start()

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

    def _on_show_me(self) -> None:
        result = self._locate_result_cache
        if not result:
            return
        self._show_me_btn.hide()
        box = result.get("box")
        img = result.get("img")
        win_info = result.get("win_info")
        self._render_locate(img, box)
        if win_info is not None:
            try:
                from ui.overlay_window import instance as _overlay
                _overlay().show_arrow(box, img.size, win_info)
            except Exception as e:
                print(f"[overlay] show_arrow failed: {e}")

    def _on_locate_result(self, result: dict) -> None:
        box = result.get("box")
        img = result.get("img")
        if box is None or img is None:
            return  # locate failed — show nothing
        self._locate_result_cache = result
        btn = QPushButton("Show me on screen")
        btn.setObjectName("showMeBtn")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self._on_show_me)
        self._bubble_layout.addWidget(btn)
        self._show_me_btn = btn

    def _render_locate(self, img: object, box: dict) -> None:
        """Draw an arrow at the matched control and show as an in-bubble thumbnail."""
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pix = QPixmap()
        pix.loadFromData(buf.getvalue(), "PNG")
        pix = pix.scaledToWidth(240, Qt.SmoothTransformation)
        dw, dh = pix.width(), pix.height()
        iw, ih = img.size

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)

        # Scale box coords to display pixel space
        bx = box["left"] / iw * dw
        by = box["top"] / ih * dh
        bw = box["width"] / iw * dw
        bh = box["height"] / ih * dh

        painter.setPen(QPen(QColor("#0a84ff"), 2))
        painter.setBrush(QColor(10, 132, 255, 60))
        painter.drawRoundedRect(QRectF(bx, by, bw, bh), 4, 4)

        # Arrow pointing down into the box from above
        tip = QPointF(bx + bw / 2, by)
        tail = QPointF(bx + bw / 2, max(by - 22, 2))
        painter.setPen(QPen(QColor("#0a84ff"), 2))
        painter.drawLine(tail, tip)
        ang = math.atan2(tip.y() - tail.y(), tip.x() - tail.x())
        for da in (math.radians(150), math.radians(-150)):
            painter.drawLine(
                tip,
                QPointF(tip.x() + 9 * math.cos(ang + da),
                        tip.y() + 9 * math.sin(ang + da)),
            )

        label = box.get("label", "")
        if label:
            painter.setFont(_system_font(9))
            fm = painter.fontMetrics()
            cw = fm.horizontalAdvance(label) + 8
            ch = fm.height() + 2
            cx = min(max(bx, 0.0), float(max(dw - cw, 0)))
            cy = by - ch - 4
            if cy < 0:
                cy = by + bh + 2
            chip = QRectF(cx, cy, cw, ch)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#0a84ff"))
            painter.drawRoundedRect(chip, 3, 3)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(chip, Qt.AlignCenter, label)

        painter.end()

        thumb = QLabel()
        thumb.setPixmap(pix)
        thumb.setStyleSheet("border-radius: 6px;")

        dismiss = QPushButton("✕")
        dismiss.setObjectName("headerBtn")
        dismiss.setFixedSize(20, 20)

        dismiss_row = QHBoxLayout()
        dismiss_row.setContentsMargins(0, 2, 0, 0)
        dismiss_row.addStretch()
        dismiss_row.addWidget(dismiss)

        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(2)
        cl.addWidget(thumb)
        cl.addLayout(dismiss_row)

        def _dismiss() -> None:
            container.hide()
            self._show_me_btn.setEnabled(True)
            self._show_me_btn.setText("Show me on screen")
            self._show_me_btn.show()
            try:
                from ui.overlay_window import instance as _overlay
                _overlay().dismiss()
            except Exception:
                pass

        dismiss.clicked.connect(_dismiss)
        self._bubble_layout.addWidget(container)
        self._locate_container = container

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
