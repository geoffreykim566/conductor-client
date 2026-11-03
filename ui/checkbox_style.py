"""Draws the checkbox square in theme.CHECKBOX instead of the Mac's accent color.

The native macOS style paints QCheckBox with the system accent color (System
Settings > Appearance) and ignores Qt's palette, so the app's checkboxes would
change color from Mac to Mac. This proxy draws only the indicator square;
the label, focus and everything else stay native.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QProxyStyle, QStyle

from ui.theme import CHECKBOX, WHITE, qcolor

_SIZE = 14.0      # native macOS checkbox square, in points
_RADIUS = 3.5


class CheckboxStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        if element != QStyle.PE_IndicatorCheckBox:
            return super().drawPrimitive(element, option, painter, widget)

        r = QRectF(option.rect)
        side = min(_SIZE, r.width(), r.height())
        box = QRectF(r.center().x() - side / 2, r.center().y() - side / 2, side, side)
        enabled = bool(option.state & QStyle.State_Enabled)
        checked = bool(option.state & QStyle.State_On)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        if not enabled:
            painter.setOpacity(0.4)
        if checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(qcolor(CHECKBOX))
            painter.drawRoundedRect(box, _RADIUS, _RADIUS)
            pen = QPen(qcolor(WHITE), side * 0.13, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            tick = QPainterPath(QPointF(box.left() + side * 0.25, box.top() + side * 0.52))
            tick.lineTo(box.left() + side * 0.43, box.top() + side * 0.70)
            tick.lineTo(box.left() + side * 0.76, box.top() + side * 0.31)
            painter.drawPath(tick)
        else:
            painter.setPen(QPen(qcolor(WHITE, 0.35), 1.0))
            painter.setBrush(qcolor(WHITE, 0.06))
            painter.drawRoundedRect(box.adjusted(0.5, 0.5, -0.5, -0.5), _RADIUS, _RADIUS)
        painter.restore()
