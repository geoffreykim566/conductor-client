"""Reusable frameless/translucent popup window.

Used for Settings, its confirm dialogs (delete history / uninstall), and the
launch-time update prompt — all centered on screen. History uses the same
base but anchors below a button instead of centering (see anchor_below).
"""
from PySide6.QtCore import QEvent, QRect, Qt, Signal
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ui.theme import ICON_BTN_SIZE


class Popup(QWidget):
    """Frameless, translucent, always-on-top popup with a titled header + close button.

    Subclasses (or callers) add their own content to `self.body`.
    """

    closed = Signal()

    def __init__(self, title: str, width: int) -> None:
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(width)

        self._panel = QWidget(self)
        self._panel.setObjectName("popupRoot")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._panel)

        panel_layout = QVBoxLayout(self._panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("sessionHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 8, 12, 8)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("sessionTitle")
        hl.addWidget(title_lbl)
        hl.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setObjectName("headerBtn")
        close_btn.setFixedSize(ICON_BTN_SIZE, ICON_BTN_SIZE)
        close_btn.clicked.connect(self._on_close)
        hl.addWidget(close_btn)
        panel_layout.addWidget(header)

        self.body = QWidget()
        panel_layout.addWidget(self.body, 1)

        self._dismiss_on_outside_click = False
        self._dismiss_ignore_widget: QWidget | None = None

    def _on_close(self) -> None:
        self.closed.emit()
        self.close()

    def _sync_panel_size(self) -> None:
        self._panel.setFixedSize(self.size())

    def resizeEvent(self, event) -> None:
        self._sync_panel_size()
        super().resizeEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Without this, a popup that isn't yet the active/key window can eat its
        # first click just activating the window (macOS), so e.g. the X button
        # doesn't register until a second click.
        self.raise_()
        self.activateWindow()

    def enable_click_outside_dismiss(self, ignore_widget: QWidget | None = None) -> None:
        """Close this popup when it loses focus to a click outside it.

        `ignore_widget` is the button (if any) that toggles this popup open —
        a click there also deactivates us, but that widget's own click handler
        already closes us, so skip our own close to avoid closing-then-
        immediately-reopening.
        """
        self._dismiss_on_outside_click = True
        self._dismiss_ignore_widget = ignore_widget

    def event(self, event) -> bool:
        if (
            event.type() == QEvent.Type.WindowDeactivate
            and self._dismiss_on_outside_click
            and self.isVisible()
            and not self._click_is_on_ignore_widget()
        ):
            self._on_close()
        return super().event(event)

    def _click_is_on_ignore_widget(self) -> bool:
        if self._dismiss_ignore_widget is None:
            return False
        top_left = self._dismiss_ignore_widget.mapToGlobal(
            self._dismiss_ignore_widget.rect().topLeft()
        )
        rect = QRect(top_left, self._dismiss_ignore_widget.size())
        return rect.contains(QCursor.pos())

    def center_on_screen(self) -> None:
        self.adjustSize()
        self._sync_panel_size()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2,
        )

    def anchor_above(self, widget: QWidget, gap: int = 8) -> None:
        """Position this popup's bottom edge `gap` px above `widget`'s top edge,
        right-aligned to `widget`'s right edge, clamped to stay on screen."""
        self.adjustSize()
        self._sync_panel_size()
        top_left = widget.mapToGlobal(widget.rect().topLeft())
        x = top_left.x() + widget.width() - self.width()
        y = top_left.y() - self.height() - gap
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = max(screen.left(), min(x, screen.right() - self.width()))
        y = max(screen.top(), y)
        self.move(x, y)

    def anchor_below(self, widget: QWidget, gap: int = 8) -> None:
        """Position this popup's top edge `gap` px below `widget`'s bottom edge,
        right-aligned to `widget`'s right edge, clamped to stay on screen."""
        self.adjustSize()
        self._sync_panel_size()
        bottom_left = widget.mapToGlobal(widget.rect().bottomLeft())
        x = bottom_left.x() + widget.width() - self.width()
        y = bottom_left.y() + gap
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = max(screen.left(), min(x, screen.right() - self.width()))
        y = min(y, screen.bottom() - self.height())
        self.move(x, y)
