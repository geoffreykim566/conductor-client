"""Right-click menu for text: our glass menu in place of Qt's QMenu (README "Context menu").

`install(app)` adds one app-wide event filter. It catches the context-menu event
for selectable labels (chat bubbles), text edits (the input field) and line
edits, and shows `ContextMenu` with the same basic items Qt's menu had.
"""
from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt
from PySide6.QtGui import QGuiApplication, QTextDocument
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.glass import GlassBackdrop, full_rect
from ui.symbols import set_symbol
from ui.theme import ICON_SIZE, MENU_RADIUS, TEXT_DIM, TEXT_SECONDARY

_MIN_WIDTH = 150
_SCREEN_MARGIN = 6
_ICON_SLOT = ICON_SIZE + 6


class ContextMenu(QWidget):
    """A glass menu like the ☰ one. `items` holds (label, symbol, action, enabled)
    tuples, or None for a divider. A click outside closes it (Qt.Popup)."""

    def __init__(self, items) -> None:
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        panel = QWidget(self)
        panel.setObjectName("menuRoot")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(1)
        for item in items:
            if item is None:
                line = QFrame()
                line.setObjectName("menuSeparator")
                line.setFixedHeight(1)
                layout.addWidget(line)
                continue
            label, symbol, action, enabled = item
            btn = QPushButton(label)
            btn.setObjectName("menuItem")
            btn.setEnabled(enabled)
            if enabled:
                btn.setCursor(Qt.PointingHandCursor)
            set_symbol(btn, symbol, ICON_SIZE, TEXT_SECONDARY if enabled else TEXT_DIM)
            # One slot for every glyph (they differ in width), so the labels line up.
            btn.setIconSize(QSize(_ICON_SLOT, _ICON_SLOT))
            btn.setText(f"  {label}")   # set_symbol drops the text; the spaces pad it off the icon
            btn.clicked.connect(lambda _=False, a=action: self._pick(a))
            layout.addWidget(btn)

        self.setMinimumWidth(_MIN_WIDTH)
        self._glass = GlassBackdrop(self, full_rect(self, MENU_RADIUS), roots=[panel])

    def _pick(self, action) -> None:
        self.close()
        action()

    def show_at(self, pos: QPoint) -> None:
        """Top-left at `pos` (global), moved back inside the screen."""
        self.adjustSize()
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry().adjusted(
            _SCREEN_MARGIN, _SCREEN_MARGIN, -_SCREEN_MARGIN, -_SCREEN_MARGIN)
        x = min(pos.x(), area.right() - self.width())
        y = pos.y() if pos.y() + self.height() <= area.bottom() else pos.y() - self.height()
        self.move(max(x, area.left()), max(y, area.top()))
        self.show()


def _copy_text(text: str) -> None:
    QGuiApplication.clipboard().setText(text)


def _label_items(label: QLabel) -> list:
    """Copy and Select All. Qt's menu also had Copy Link Location; it's left out:
    the links in replies are explain mode's terms, which aren't web addresses."""
    def select_all() -> None:
        text = label.text()
        if Qt.mightBeRichText(text) and label.textFormat() != Qt.PlainText:
            doc = QTextDocument()
            doc.setHtml(text)
            text = doc.toPlainText()
        label.setSelection(0, len(text))

    return [
        ("Copy", "doc.on.doc", lambda: _copy_text(label.selectedText()), label.hasSelectedText()),
        None,
        ("Select All", "character.textbox", select_all, bool(label.text())),
    ]


def _edit_items(edit) -> list:
    """Undo/Redo, Cut/Copy/Paste, Select All, for QTextEdit, QPlainTextEdit and QLineEdit.
    Paste goes through the widget's own paste(), so the input field's image paste still works."""
    if isinstance(edit, QLineEdit):
        has_sel, read_only = edit.hasSelectedText(), edit.isReadOnly()
        can_undo, can_redo = edit.isUndoAvailable(), edit.isRedoAvailable()
        can_paste = not read_only and bool(QGuiApplication.clipboard().text())
        has_text = bool(edit.text())
    else:
        has_sel, read_only = edit.textCursor().hasSelection(), edit.isReadOnly()
        doc = edit.document()
        can_undo, can_redo = doc.isUndoAvailable(), doc.isRedoAvailable()
        can_paste = not read_only and edit.canPaste()
        has_text = not doc.isEmpty()
    copy = ("Copy", "doc.on.doc", edit.copy, has_sel)
    select_all = ("Select All", "character.textbox", edit.selectAll, has_text)
    if read_only:
        return [copy, None, select_all]
    return [
        ("Undo", "arrow.uturn.backward", edit.undo, can_undo),
        ("Redo", "arrow.uturn.forward", edit.redo, can_redo),
        None,
        ("Cut", "scissors", edit.cut, has_sel),
        copy,
        ("Paste", "doc.on.clipboard", edit.paste, can_paste),
        None,
        select_all,
    ]


def _target(obj):
    """The widget whose menu this event is for, or None to leave it to Qt.
    A text edit's event arrives on its viewport first."""
    if isinstance(obj, QLabel):
        return obj if obj.textInteractionFlags() & Qt.TextSelectableByMouse else None
    if isinstance(obj, QLineEdit):
        return obj
    parent = obj.parent() if isinstance(obj, QWidget) else None
    if isinstance(parent, (QTextEdit, QPlainTextEdit)) and obj is parent.viewport():
        return parent
    return None


class _ContextMenuFilter(QObject):
    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.Type.ContextMenu:
            return False
        target = _target(obj)
        if target is None or target.contextMenuPolicy() != Qt.DefaultContextMenu:
            return False
        items = _label_items(target) if isinstance(target, QLabel) else _edit_items(target)
        ContextMenu(items).show_at(event.globalPos())
        return True


def install(app) -> None:
    """Show our menu for text widgets app-wide. Call once, after the QApplication exists."""
    app._context_menu_filter = _ContextMenuFilter(app)   # kept alive with the app
    app.installEventFilter(app._context_menu_filter)
