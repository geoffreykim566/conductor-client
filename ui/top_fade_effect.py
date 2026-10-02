"""TopEdgeFadeEffect: fades a widget's rendered content to transparent at its top edge."""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QGraphicsEffect

_FADE_HEIGHT = 24  # px the fade takes; it always starts at chat_view's own top edge


class TopEdgeFadeEffect(QGraphicsEffect):
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
