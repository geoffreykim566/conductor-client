"""MessageWidget: one chat bubble (user or assistant) plus whatever attaches under it."""
import base64

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ui.message.rating import RatingMixin
from ui.message.research_prompt import ResearchPromptMixin
from ui.message.sources import SourcesMixin
from ui.message.styles import system_font
from ui.message.walkthrough_card import WalkthroughCard
from ui.theme import BUTTON_RADIUS, SCROLLBAR_GUTTER, TEXT_MUTED


class MessageWidget(RatingMixin, ResearchPromptMixin, SourcesMixin, QWidget):
    """A chat bubble. Use append_text() to grow streamed assistant messages."""

    def __init__(self, role: str, text: str = "", images_b64: list[str] | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self._role = role

        # Vertical stack so a rating row can sit *under* the bubble (like Claude),
        # outside the response itself.
        # Right margin trimmed by SCROLLBAR_GUTTER for user bubbles only:
        # they're right-aligned, so chat_view.py's scrollbar gutter adds to
        # their right edge (see README "Bubble margins").

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
        self._text_label.setFont(system_font(13))
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
        self._wt_card: WalkthroughCard | None = None

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

    def mark_cancelled(self) -> None:
        """Esc mid-turn. A bubble with no real text yet just shows the
        status-style 'Cancelled'; one that already streamed part of an
        answer keeps it and gets the marker appended."""
        self.hide_research_prompt()
        if getattr(self, "_has_status", False) or not self._text:
            self.set_status_text("Cancelled")
        else:
            self.append_text("\n\n[cancelled]")

    def setup_walkthrough(self, steps: list, *, auto: bool = False, destructive: bool = False) -> None:
        """Render a walkthrough/action card inside the bubble (see WalkthroughCard)."""
        if self._role != "assistant" or not steps:
            return
        self._wt_card = WalkthroughCard(steps, auto=auto, destructive=destructive)
        self._bubble_layout.addWidget(self._wt_card)

    def wt_enter(self) -> None:
        """Enter / the card's main button (see WalkthroughCard.enter)."""
        if self._wt_card is not None:
            self._wt_card.enter()

    def force_end_walkthrough(self) -> None:
        """External safety hook: stop any active walkthrough before this
        widget (or the app) is torn down. Safe to call on any MessageWidget,
        even one that never set up a walkthrough card -- call this before
        deleting/clearing message widgets or on app quit.
        """
        if self._wt_card is not None:
            self._wt_card.force_end()
