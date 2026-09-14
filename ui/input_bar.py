"""Input bar: pending attachment preview, new-chat/history icons, text input, send button.

Also doubles as the window's drag handle — clicking and dragging any part of
this bar's own background (not the text edit or a button), or of .controls's
own background (not one of its icons), moves the window, since the outer
window has no native titlebar. .controls reads as the closest thing to one
(icons left/right, blank space between), so it's the primary drag target in
practice -- see the comment where it's built, below.
"""
import base64

from PySide6.QtCore import QEvent, QPoint, Qt, Signal
from PySide6.QtGui import QFontMetrics, QKeyEvent, QMouseEvent, QPixmap, QTextOption
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.theme import BORDER, CONTROL_SIZE, ICON_BTN_SIZE, INPUT_PILL_PADDING


class _ChatTextEdit(QTextEdit):
    """QTextEdit that sends on Enter and inserts newline on Shift+Enter."""

    submit = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submit.emit()
                return
        super().keyPressEvent(event)


class InputBar(QWidget):
    """Pending-attachment row + new-chat/history icons + text + send button.

    Emits send(text, list_of_b64_images) when the user submits.
    Emits enter_empty when Enter is pressed with no text (walkthrough advance).
    Emits new_chat_requested / history_requested from their respective icons.
    """

    _DEFAULT_PLACEHOLDER = "Ask anything about Logic Pro…"

    send = Signal(str, list)
    enter_empty = Signal()
    new_chat_requested = Signal()
    history_requested = Signal()
    minimize_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pending_images: list[str] = []
        self._drag_offset: QPoint | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 10)
        root.setSpacing(0)

        # Invisible layout container (background: transparent, ui/style.py) --
        # only the #inputBubble pill inside it is actually drawn. The event
        # filter makes clicking its blank area drag the window.
        self._panel = QWidget()
        self._panel.setObjectName("inputPanel")
        self._panel.installEventFilter(self)
        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(2)
        root.addWidget(self._panel)

        # Attachment preview row (hidden when empty)
        self._attachments_row = QWidget()
        self._attachments_layout = QHBoxLayout(self._attachments_row)
        self._attachments_layout.setContentsMargins(0, 0, 0, 0)
        self._attachments_layout.setSpacing(4)
        self._attachments_row.hide()
        panel_layout.addWidget(self._attachments_row)

        # Controls row (new-chat/history/remaining-count/minimize/close) --
        # NOT part of this panel. Sits on the bubbles backdrop panel instead
        # (ChatWindow adds self.controls above the chat view, see
        # ChatWindow.__init__), a standalone widget so it can be placed there
        # while everything else about InputBar (text/send, signals) stays
        # exactly as before.
        #
        # Also the window's main drag handle -- installEventFilter below,
        # same _drag_press/_drag_move/_drag_release as _panel uses. Until
        # 6b28d41 (2026-09-12) that job fell to the margin outside _panel
        # (then a real, generously-sized strip -- CONTENT_LEFT_INSET); that
        # commit zeroed the margin out (it was ALSO an invisible dead strip
        # past the window's visible edge, catching stray clicks -- the actual
        # bug it fixed), silently deleting the only practical drag target and
        # leaving users unable to move the window. Routing drag through this
        # row's own real background instead of a separately-tracked margin
        # means there's nothing to keep in sync by hand -- Qt's own hit
        # testing already gives every icon/label priority over this widget,
        # so the draggable area can't drift from the visible layout the way
        # the old inset did.
        self.controls = QWidget()
        self.controls.installEventFilter(self)
        controls_row = QHBoxLayout(self.controls)
        # Left/top padding clears the bubbles panel's rounded corner. This
        # is the ONLY thing controlling the gap to chat_view below
        # (ChatWindow's main layout has zero spacing there deliberately, see
        # ChatWindow.__init__), not stacked with layout spacing like before.
        # Bottom smaller than top despite equal-margin math suggesting they
        # should read the same -- found live 2026-09-04 that equal numeric
        # margins still looked bottom-heavy (likely the row's own content,
        # e.g. label line-height, isn't perfectly vertically symmetric),
        # tuned down by feel rather than by a formula.
        controls_row.setContentsMargins(10, 10, 12, 7)
        controls_row.setSpacing(6)

        new_btn = QPushButton("✦")
        new_btn.setObjectName("headerBtn")
        new_btn.setFixedSize(ICON_BTN_SIZE, ICON_BTN_SIZE)
        new_btn.clicked.connect(self.new_chat_requested)
        controls_row.addWidget(new_btn, 0, Qt.AlignVCenter)

        hist_btn = QPushButton("☰")
        hist_btn.setObjectName("headerBtn")
        hist_btn.setFixedSize(ICON_BTN_SIZE, ICON_BTN_SIZE)
        hist_btn.clicked.connect(self.history_requested)
        controls_row.addWidget(hist_btn, 0, Qt.AlignVCenter)
        self.history_button = hist_btn

        controls_row.addStretch()

        self._remaining_label = QLabel("")
        self._remaining_label.setObjectName("remainingLabel")
        self._remaining_label.hide()
        controls_row.addWidget(self._remaining_label, 0, Qt.AlignVCenter)

        controls_row.addStretch()

        self._min_btn = QPushButton("—")
        self._min_btn.setObjectName("headerBtn")
        self._min_btn.setFixedSize(ICON_BTN_SIZE, ICON_BTN_SIZE)
        self._min_btn.clicked.connect(self.minimize_requested)
        controls_row.addWidget(self._min_btn, 0, Qt.AlignVCenter)

        self._close_btn = QPushButton("✕")
        self._close_btn.setObjectName("headerBtn")
        self._close_btn.setFixedSize(ICON_BTN_SIZE, ICON_BTN_SIZE)
        self._close_btn.clicked.connect(self.close_requested)
        controls_row.addWidget(self._close_btn, 0, Qt.AlignVCenter)

        # Single rounded-rect bubble holding the text field and send button —
        # the only boxed element left in this panel now that the controls
        # row above has moved out onto the bubbles backdrop panel instead.
        bubble = QWidget()
        bubble.setObjectName("inputBubble")
        bubble_row = QHBoxLayout(bubble)
        bubble_row.setContentsMargins(
            INPUT_PILL_PADDING, INPUT_PILL_PADDING, INPUT_PILL_PADDING, INPUT_PILL_PADDING
        )
        bubble_row.setSpacing(INPUT_PILL_PADDING)

        self._text = _ChatTextEdit()
        self._text.setObjectName("bareInput")
        self._text.setPlaceholderText(self._DEFAULT_PLACEHOLDER)
        # QTextEdit's placeholder is painted from the document's default text
        # option, not the cursor-based setAlignment(). Left-aligned so both
        # the placeholder and the cursor start at the field's left edge
        # rather than the middle. Vertical centering (QTextDocument has no
        # concept of it) is handled manually via viewport margins below.
        self._text.document().setDefaultTextOption(QTextOption(Qt.AlignLeft))
        self._text.document().setDocumentMargin(0)
        self._text.setFixedHeight(CONTROL_SIZE)
        line_height = QFontMetrics(self._text.font()).height()
        # Bottom explicitly computed as the remainder rather than hardcoded 0
        # -- a bottom margin of 0 left the leftover space as implicit,
        # top-aligned-within-the-viewport blank room instead, which read as
        # visibly bigger than the top margin (found live 2026-09-04).
        extra = max(0, CONTROL_SIZE - line_height)
        top_margin = extra // 2
        bottom_margin = extra - top_margin
        self._text.setViewportMargins(12, top_margin, 4, bottom_margin)
        self._text.submit.connect(self._on_send)
        bubble_row.addWidget(self._text, 1)

        self._send_btn = QPushButton("↑")
        self._send_btn.setObjectName("sendBtn")
        self._send_btn.setFixedSize(CONTROL_SIZE, CONTROL_SIZE)
        self._send_btn.clicked.connect(self._on_send)
        bubble_row.addWidget(self._send_btn)

        panel_layout.addWidget(bubble)

    def add_pending_image(self, b64: str) -> None:
        """Add an image to the pending attachments preview."""
        self._pending_images.append(b64)
        idx = len(self._pending_images) - 1

        thumb_container = QWidget()
        layout = QVBoxLayout(thumb_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        pix = QPixmap()
        pix.loadFromData(base64.b64decode(b64), "PNG")
        thumb = QLabel()
        thumb.setPixmap(pix.scaledToHeight(40, Qt.SmoothTransformation))
        thumb.setStyleSheet(f"border: 1px solid {BORDER}; border-radius: 3px;")
        layout.addWidget(thumb)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedHeight(14)
        remove_btn.setStyleSheet("font-size: 9px;")
        remove_btn.clicked.connect(lambda _=False, i=idx: self._remove_pending(i))
        layout.addWidget(remove_btn)

        self._attachments_layout.addWidget(thumb_container)
        self._attachments_row.show()

    def set_remaining(self, remaining: int | None) -> None:
        """Show how many free messages the user has left, or hide when unknown."""
        if remaining is None or remaining < 0:
            self._remaining_label.hide()
            return
        noun = "message" if remaining == 1 else "messages"
        self._remaining_label.setText(f"{remaining} {noun} left")
        self._remaining_label.show()

    def set_enabled_inputs(self, enabled: bool) -> None:
        self._text.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)

    def set_placeholder(self, text: str | None = None) -> None:
        """Swap the empty-field hint; None restores the default. Used while a
        turn is in flight ("Press Esc to cancel") -- the field is empty and
        disabled then, so the placeholder is the one line the user still
        reads there."""
        self._text.setPlaceholderText(text or self._DEFAULT_PLACEHOLDER)

    def _on_send(self) -> None:
        text = self._text.toPlainText().strip()
        if not text:
            self.enter_empty.emit()
            return
        images = list(self._pending_images)
        self._pending_images.clear()
        self._clear_attachments_ui()
        self._text.clear()
        self.send.emit(text, images)

    def _remove_pending(self, idx: int) -> None:
        if 0 <= idx < len(self._pending_images):
            self._pending_images.pop(idx)
            self._rebuild_attachments_ui()

    def _clear_attachments_ui(self) -> None:
        while self._attachments_layout.count():
            item = self._attachments_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._attachments_row.hide()

    def _rebuild_attachments_ui(self) -> None:
        images = list(self._pending_images)
        self._pending_images.clear()
        self._clear_attachments_ui()
        for b64 in images:
            self.add_pending_image(b64)

    # --- window drag ---
    # Only fires when the click lands on background with no interactive
    # child under it (Qt routes events to a child widget first when one is
    # under the cursor), so text selection in the input and the icon/send
    # buttons are unaffected. `_panel` is a separate child widget covering
    # most of the bar, so it needs its own event filter below — a plain
    # override here only catches the thin margin outside `_panel`.
    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._drag_press(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._drag_move(event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_release()
        super().mouseReleaseEvent(event)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._panel or obj is self.controls:
            t = event.type()
            if t == QEvent.Type.MouseButtonPress:
                self._drag_press(event)
            elif t == QEvent.Type.MouseMove:
                self._drag_move(event)
            elif t == QEvent.Type.MouseButtonRelease:
                self._drag_release()
        return super().eventFilter(obj, event)

    def _drag_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()

    def _drag_move(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)

    def _drag_release(self) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            if hasattr(self.window(), "persist_geometry"):
                self.window().persist_geometry()
