"""Scrolling chat history view."""
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QGraphicsEffect,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from config import CONTENT_LEFT_INSET
from ui.message_widget import MessageWidget

MONO = '"Menlo", monospace'
_QWIDGETSIZE_MAX = 16777215  # Qt's own constant for "no max height set"

_FADE_HEIGHT = 24  # how many px the transition takes, not where it starts --
# it always starts at chat_view's own top edge (confirmed live 2026-09-04:
# exactly 44px from the window top, right below the controls row). A bigger
# number stretches the same 0%->100% transition further down, it doesn't move
# the start point higher; kept small for a fast, snappy fade right under the
# controls instead of a slow one bleeding deep into the second bubble.
# (2026-09-04) -- 40 was tuned for the old drag-header, and stayed too tight
# a transition once controls moved: bubbles read as fully visible right up to
# the last ~40px before chat_view's own top edge, well below the controls'
# bottom border, instead of visibly fading out sooner.
_SCROLLBAR_IDLE_MS = 600  # how long after the last scroll before the handle fades back out
# Fraction of the viewport height a new turn's user message is anchored to
# from the top, leaving the remainder below for the response to render into.
# Not the true bottom — pinning to the true bottom (the old approach) meant
# every streamed chunk had to re-scroll to follow it, dragging the already-
# read top further up past the fade as the bubble grew. Anchoring once at
# turn start and then holding still lets the bubble grow downward in place
# instead; a response that outgrows the reserved space just extends below
# the fold, same end state as before, without the per-chunk rescroll.
_TURN_ANCHOR_FRACTION = 1 / 3


class _TopEdgeFadeEffect(QGraphicsEffect):
    """Fades the widget's own rendered content to nothing at its top edge —
    erases pixel alpha rather than painting a color over it, so what's
    revealed is the window's real transparency (Logic Pro/desktop showing
    through), not a tinted overlay."""

    def draw(self, painter: QPainter) -> None:
        result_pair = self.sourcePixmap(Qt.CoordinateSystem.LogicalCoordinates)
        if isinstance(result_pair, tuple):
            pixmap, offset = result_pair
        else:
            pixmap, offset = result_pair, QPoint(0, 0)
        if pixmap.isNull():
            painter.drawPixmap(offset, pixmap)
            return

        fade_h = min(_FADE_HEIGHT, pixmap.height())
        if fade_h <= 0:
            painter.drawPixmap(offset, pixmap)
            return

        result = pixmap.copy()
        p = QPainter(result)
        gradient = QLinearGradient(0, 0, 0, fade_h)
        gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 255))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        p.fillRect(0, 0, result.width(), fade_h, gradient)
        p.end()

        painter.drawPixmap(offset, result)


class ChatView(QWidget):
    """Scrollable column of MessageWidget bubbles with an empty-state placeholder."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setGraphicsEffect(_TopEdgeFadeEffect(self))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── placeholder shown when chat is empty ──────────────────
        self._placeholder = QLabel("")
        self._placeholder.setObjectName("chatPlaceholder")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setWordWrap(True)
        outer.addWidget(self._placeholder, 1)

        # ── scrollable message list ───────────────────────────────
        # QScrollArea's internal viewport (a separate child widget Qt
        # creates under the hood) has autoFillBackground on by default,
        # painting an opaque palette color — the transparent rule in the
        # app stylesheet only reaches the QScrollArea frame itself, not the
        # viewport, so without this the whole scroll region shows up as a
        # solid backdrop behind the message bubbles. A plain widget
        # attribute (not a stylesheet rule) so it can't affect how the
        # QApplication stylesheet colors the message bubbles underneath.
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.viewport().setAutoFillBackground(False)

        self._container = QWidget()
        self._container.setAutoFillBackground(False)
        self._layout = QVBoxLayout(self._container)
        # Left margin matches input_bar.py's own left inset (CONTENT_LEFT_INSET)
        # so left-aligned assistant bubbles stay inside the bubbles backdrop
        # panel (chat_window.py's paintEvent, which aligns to the input bar's
        # actual panel bounds) instead of spilling past its left edge (found
        # live 2026-09-04, screenshot feedback after that panel was narrowed).
        self._layout.setContentsMargins(CONTENT_LEFT_INSET, 14, 0, 0)
        self._layout.setSpacing(2)
        # A real widget rather than layout.addStretch()'s QSpacerItem, so it
        # can be frozen at a specific fixed height for the duration of a turn
        # (see _apply_turn_anchor) instead of always expanding to absorb
        # whatever space is left. Expanding by default: absorbs leftover
        # space above the messages, so a short/idle conversation sits flush
        # against the input bar at the bottom (like a normal chat log)
        # instead of floating near the top with dead space below it.
        # Persists across clear() (New Chat) rather than being recreated.
        self._flex_spacer = QWidget()
        self._flex_spacer.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        # Lopsided stretch factor vs. the trailing spacer below (1000:1) so
        # this one still wins essentially all the slack while idle/resting,
        # keeping the flush-at-bottom look for a short conversation between
        # turns — the trailing spacer only needs to be non-zero, not equal.
        self._layout.addWidget(self._flex_spacer, 1000)
        # Trailing counterpart, always kept as the very last layout item (new
        # messages are inserted before it, never appended after). Needed
        # because MessageWidget's own bubble uses QSizePolicy.Minimum on its
        # vertical axis (growable, just not preferred to) — when the leading
        # spacer above is frozen smaller than the viewport during a turn,
        # Qt still has to hand the container's forced-viewport-height leftover
        # to *someone*, and Minimum-policy siblings are eligible for it too.
        # Without a real Expanding claimant at the end, that leftover was
        # landing on the message bubble itself instead of neutral blank
        # space, visibly stretching it. An Expanding widget always outranks
        # a Minimum one for surplus space (regardless of stretch factor —
        # factor only splits space between same-tier competitors), so this
        # reliably wins that space instead.
        self._trailing_spacer = QWidget()
        self._trailing_spacer.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self._layout.addWidget(self._trailing_spacer, 1)
        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll, 1)

        # Handle is transparent by default (see style.py's `scrolling` property
        # selector) and only painted while actively scrolling, macOS-overlay-
        # style — the 4px track itself always reserves its space either way.
        self._scrollbar_hide_timer = QTimer(self)
        self._scrollbar_hide_timer.setSingleShot(True)
        self._scrollbar_hide_timer.timeout.connect(self._hide_scrollbar)
        self._scroll.verticalScrollBar().valueChanged.connect(self._on_scrolled)

        self._current_assistant: MessageWidget | None = None
        self._active_wt_widget: MessageWidget | None = None
        self._scroll.hide()

    def _insert_before_trailing_spacer(self, widget: QWidget) -> None:
        self._layout.insertWidget(self._layout.count() - 1, widget)

    def add_user_message(self, text: str, images_b64: list[str]) -> None:
        self._show_messages()
        widget = MessageWidget("user", text=text, images_b64=images_b64)
        self._insert_before_trailing_spacer(widget)
        self._anchor_new_turn(widget)

    def begin_assistant_message(self) -> None:
        self._show_messages()
        self._current_assistant = MessageWidget("assistant", text="")
        self._insert_before_trailing_spacer(self._current_assistant)
        # No scroll here — the turn's anchor was already set by the user
        # message right above this one; the empty bubble starts inside that
        # reserved space and just grows into it as chunks arrive.

    def append_to_assistant(self, chunk: str) -> None:
        if self._current_assistant is None:
            return
        self._current_assistant.append_text(chunk)
        # No re-scroll per chunk (deliberate, see _anchor_new_turn) — the
        # view holds still for the whole turn; a response that outgrows the
        # reserved space below the anchor just extends past the visible
        # bottom instead of dragging the top further up as it grows.

    def set_assistant_status(self, text: str) -> None:
        if self._current_assistant is not None:
            self._current_assistant.set_status_text(text)

    def set_assistant_tier(self, tier: str, sources: list) -> None:
        if self._current_assistant is not None:
            self._current_assistant.set_source_tier(tier)
            self._current_assistant.set_sources(sources)

    def setup_walkthrough_card(self, steps: list) -> None:
        if self._current_assistant is not None:
            self._current_assistant.setup_walkthrough(steps)
            self._active_wt_widget = self._current_assistant

    def wt_enter(self) -> None:
        if self._active_wt_widget is not None:
            self._active_wt_widget.wt_enter()

    def has_active_walkthrough(self) -> bool:
        return self._active_wt_widget is not None

    def force_end_active_walkthrough(self) -> None:
        """Safety hook for app quit — stop any running walkthrough thread
        before QApplication teardown destroys it (see clear())."""
        if self._active_wt_widget is not None:
            self._active_wt_widget.force_end_walkthrough()

    def show_rating(self, on_rate, initial: int = 0) -> None:
        if self._current_assistant is not None:
            self._current_assistant.enable_rating(on_rate, initial=initial)

    def end_assistant_message(self) -> None:
        self._current_assistant = None
        # The spacer frozen by this turn's _apply_turn_anchor is deliberately
        # left frozen here rather than unfrozen back to flexible: unfreezing
        # right when a short response finishes would let it snap back to its
        # natural (larger) expanding size, which shrinks the scrollable range
        # and forces the scrollbar to auto-clamp down — a visible snap-to-
        # bottom with no explicit scroll call behind it. Left frozen until
        # the next turn recomputes it fresh (add_user_message) or New Chat
        # unfreezes it (clear()).

    def clear(self) -> None:
        # Stop any running walkthrough thread before its owning widget gets
        # deleteLater()'d below — Qt6 aborts the process if a QThread is
        # still running when its QObject is destroyed.
        if self._active_wt_widget is not None:
            self._active_wt_widget.force_end_walkthrough()
        # Index 0 is _flex_spacer, the last index is _trailing_spacer — both
        # kept in the layout (not deleted) so they don't need recreating;
        # the leading one is just unfrozen back to its normal expanding
        # behavior below. Only the message widgets between them get wiped.
        while self._layout.count() > 2:
            item = self._layout.takeAt(1)
            w = item.widget()
            if w:
                w.deleteLater()
        self._unfreeze_spacer()
        self._current_assistant = None
        self._active_wt_widget = None
        self._scroll.verticalScrollBar().setValue(0)
        self._scroll.hide()
        self._placeholder.show()

    def load_history(self, messages: list, on_rate=None) -> None:
        self.clear()
        for msg in messages:
            widget = MessageWidget(msg.role, text=msg.text, images_b64=[])
            self._insert_before_trailing_spacer(widget)
            if on_rate and msg.role == "assistant" and msg.event_id:
                widget.enable_rating(
                    lambda v, m=msg: on_rate(m, v), initial=msg.rating
                )
        if messages:
            self._show_messages()
        self._scroll_to_bottom()

    def _show_messages(self) -> None:
        self._placeholder.hide()
        self._scroll.show()

    def _on_scrolled(self, _value: int) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setProperty("scrolling", True)
        bar.style().unpolish(bar)
        bar.style().polish(bar)
        self._scrollbar_hide_timer.start(_SCROLLBAR_IDLE_MS)
        # QScrollArea scrolls its viewport by blitting directly, which never
        # asks ChatView's own QGraphicsEffect (_TopEdgeFadeEffect) to
        # recompute -- without this, the fade stayed frozen at whatever it
        # last rendered instead of following newly-scrolled-in content (found
        # live 2026-09-04: changing _FADE_HEIGHT had no visible effect at all).
        self.update()

    def _hide_scrollbar(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setProperty("scrolling", False)
        bar.style().unpolish(bar)
        bar.style().polish(bar)

    def _scroll_to_bottom(self) -> None:
        """Snap straight to the true bottom — for loading existing history,
        not for a turn that's about to generate (see _anchor_new_turn)."""
        QTimer.singleShot(0, self._apply_bottom_scroll)

    def _apply_bottom_scroll(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _anchor_new_turn(self, user_widget: QWidget) -> None:
        """Position a freshly sent user message about _TURN_ANCHOR_FRACTION
        down the viewport instead of flush at the bottom, leaving the
        remainder below for the response to render into. Set once per turn
        and then left alone — see append_to_assistant for why."""
        QTimer.singleShot(0, lambda: self._apply_turn_anchor(user_widget))

    def _apply_turn_anchor(self, user_widget: QWidget) -> None:
        viewport_h = self._scroll.viewport().height()
        widget_top = user_widget.mapTo(self._container, QPoint(0, 0)).y()
        # Height of any real conversation content above this turn (prior
        # messages), i.e. everything the still-flexible spacer's current
        # natural size does NOT account for.
        content_above = widget_top - self._flex_spacer.height()

        # Freeze the spacer at whatever height places the widget at the
        # target fraction from the top. For a short/fresh conversation this
        # is a real positive height, which also matters beyond just this
        # turn's position: QScrollArea's setWidgetResizable(True) keeps the
        # container at least viewport-tall regardless, and with no trailing
        # stretch to soak up the difference, freezing this leading gap
        # *smaller* than its natural size pushes that same leftover space to
        # the BOTTOM of the container instead — exactly the room the
        # response needs to grow into, with no separate margin trick
        # required. For an already-long conversation this clamps to 0 (the
        # spacer was already contributing nothing), and the scroll below
        # does the real work instead.
        target_spacer_h = max(0, int(viewport_h * _TURN_ANCHOR_FRACTION) - content_above)
        self._flex_spacer.setFixedHeight(target_spacer_h)

        new_widget_top = target_spacer_h + content_above
        target_scroll = new_widget_top - int(viewport_h * _TURN_ANCHOR_FRACTION)
        bar = self._scroll.verticalScrollBar()
        bar.setValue(max(0, min(target_scroll, bar.maximum())))

    def _unfreeze_spacer(self) -> None:
        self._flex_spacer.setMinimumHeight(0)
        self._flex_spacer.setMaximumHeight(_QWIDGETSIZE_MAX)
        self._flex_spacer.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
