"""Glossary terms in an assistant reply: underlined, and a click shows the definition (mixin for MessageWidget)."""
import html

from PySide6.QtCore import QEvent, QPoint, Qt, QUrl
from PySide6.QtGui import QCursor, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from ui.message.styles import system_font
from ui.glass import GlassBackdrop, full_rect
from ui.motion import fade_window_in
from ui.theme import LINK, POPUP_RADIUS, TEXT

_POPUP_WIDTH = 260


def valid_terms(text: str, terms: list) -> list[dict]:
    """The server's term spans that fit `text`, in order and not overlapping."""
    out, last_end = [], 0
    for t in sorted((t for t in terms or [] if isinstance(t, dict)), key=lambda t: t.get("start", -1)):
        start, end = t.get("start"), t.get("end")
        if not (isinstance(start, int) and isinstance(end, int)) or not t.get("definition"):
            continue
        if last_end <= start < end <= len(text):
            out.append(t)
            last_end = end
    return out


def terms_html(text: str, terms: list[dict]) -> str:
    """`text` as rich text with each term a `term:<i>` link, line breaks kept."""
    parts, pos = [], 0
    for i, t in enumerate(terms):
        parts.append(html.escape(text[pos:t["start"]]))
        parts.append(f'<a href="term:{i}" style="color:{TEXT}; text-decoration: underline;">'
                     f'{html.escape(text[t["start"]:t["end"]])}</a>')
        pos = t["end"]
    parts.append(html.escape(text[pos:]))
    return '<div style="white-space: pre-wrap;">' + "".join(parts) + "</div>"


class TermPopup(QWidget):
    """Just the definition and, when the entry has a source, a Read more link: no title, no
    close button. A click anywhere else in the app closes it (not focus loss: the window it
    opened over takes focus straight back)."""

    _open: "TermPopup | None" = None   # one at a time

    def __init__(self, term: dict) -> None:
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(_POPUP_WIDTH)
        # The box goes on a child: a translucent top-level never paints its own stylesheet background.
        self._panel = QWidget(self)
        self._panel.setObjectName("popupRoot")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._panel)
        layout = QVBoxLayout(self._panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        definition = QLabel(term.get("definition", ""))
        definition.setWordWrap(True)
        definition.setFont(system_font(13))
        definition.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(definition)
        if term.get("url"):
            source = term.get("source") or "the source"
            more = QLabel(f'<a href="{html.escape(term["url"])}" style="color:{LINK}; text-decoration:none;">'
                          f'Read more on {html.escape(source)} ↗</a>')
            more.setFont(system_font(12))
            more.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
            layout.addWidget(more)
        self._glass = GlassBackdrop(self, full_rect(self, POPUP_RADIUS), roots=[self._panel])

    @classmethod
    def show_for(cls, term: dict, at: QPoint) -> None:
        if cls._open is not None:
            cls._open.close()
        popup = cls(term)
        cls._open = popup
        layout = popup.layout()
        popup.resize(_POPUP_WIDTH, layout.totalHeightForWidth(_POPUP_WIDTH) if layout.hasHeightForWidth()
                     else popup.sizeHint().height())
        popup._panel.setFixedSize(popup.size())
        # Just below the click, kept on screen.
        screen = (QGuiApplication.screenAt(at) or QGuiApplication.primaryScreen()).availableGeometry()
        x = min(max(at.x() - 20, screen.left() + 8), screen.right() - popup.width() - 8)
        y = at.y() + 14
        if y + popup.height() > screen.bottom() - 8:
            y = at.y() - popup.height() - 8
        popup.move(x, y)
        popup.show()
        fade_window_in(popup)
        QApplication.instance().installEventFilter(popup)

    def eventFilter(self, obj, e) -> bool:
        if e.type() == QEvent.MouseButtonPress and not self.frameGeometry().contains(e.globalPosition().toPoint()):
            self.close()
        return False

    def closeEvent(self, event) -> None:
        QApplication.instance().removeEventFilter(self)
        if TermPopup._open is self:
            TermPopup._open = None
        super().closeEvent(event)


class TermsMixin:
    """Needs `self._role`, `self._text` and `self._text_label` from MessageWidget."""

    def set_terms(self, terms: list) -> None:
        """Underline the reply's glossary terms. Call once the text is fully revealed."""
        if self._role != "assistant":
            return
        self._terms = valid_terms(self._text, terms)
        if not self._terms:
            return
        label: QLabel = self._text_label
        label.setTextFormat(Qt.RichText)
        label.setText(terms_html(self._text, self._terms))
        label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        if not getattr(self, "_terms_connected", False):
            label.linkActivated.connect(self._on_term_clicked)
            self._terms_connected = True

    def _on_term_clicked(self, href: str) -> None:
        if not href.startswith("term:"):
            return
        i = int(href.split(":", 1)[1])
        if 0 <= i < len(self._terms):
            TermPopup.show_for(self._terms[i], QCursor.pos())
