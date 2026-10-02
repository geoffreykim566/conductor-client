"""Live overlay: draws a click-through arrow above a Logic plugin window.

Singleton — get the instance via overlay_window.instance(). Call show_arrow() on
a successful locate result; call dismiss() to hide. The overlay follows the plugin
window every 250 ms and hides automatically when Logic stops being frontmost.
"""
import math

import objc  # noqa: F401 — used in _ns_window via objc_object

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from core.capture.window_capture import find_all_logic_pro_windows
from ui.theme import ACCENT, WHITE, qcolor

_BLUE = qcolor(ACCENT)

_singleton: "OverlayWindow | None" = None


def instance() -> "OverlayWindow":
    global _singleton
    if _singleton is None:
        _singleton = OverlayWindow()
    return _singleton


class OverlayWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._arrow_tip: QPointF | None = None
        self._arrow_tail: QPointF | None = None
        self._menu_mode: bool = False
        self._label: str = ""
        self._win_info: dict | None = None
        self._screen_origin = QPoint(0, 0)

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._follow)

    # ------------------------------------------------------------------
    # Public API

    def show_arrow(self, box: dict, img_size: tuple[int, int],
                   win_info: dict) -> None:
        """Place and show an arrow pointing at box (in OCR pixel space).

        img_size: (img_w, img_h) — pixel dims of the OCR capture.
        win_info: kCGWindowBounds dict from the capture (screen points).
        """
        self._win_info = win_info
        self._img_size = img_size
        self._box = box
        self._label = box.get("label", "")
        self._arrow_tail = None
        self._menu_mode = False
        self._position_on_screen()
        self.show()
        self._raise_above_layer8()
        self._timer.start()

    def show_menu_arrow(self, box: dict, img_size: tuple[int, int],
                        win_info: dict) -> None:
        """Show an arrow to the side of a menu window.

        Positions tip at the menu's edge (left or right, whichever has more
        screen space) at the item's y-coordinate so the arrow never overlaps
        the layer-101 menu window.
        """
        self._win_info = win_info
        self._img_size = img_size
        self._box = box
        self._label = box.get("label", "")
        self._menu_mode = True
        self._position_menu_arrow()
        self.show()
        self._raise_above_layer8()
        self._timer.start()

    def show_static_arrow(self, tip_x_pt: float, tip_y_pt: float, label: str = "") -> None:
        """Show an upward arrow at a fixed screen position (screen points, primary screen).

        Used for menu bar items: tip points at the item, tail hangs 40pt below.
        """
        screen = (QGuiApplication.screenAt(QPoint(int(tip_x_pt), int(tip_y_pt)))
                  or QGuiApplication.primaryScreen())
        geo = screen.geometry()
        self._screen_origin = geo.topLeft()
        local_x = tip_x_pt - geo.x()
        local_y = tip_y_pt - geo.y()
        self._arrow_tip = QPointF(local_x, local_y)
        self._arrow_tail = QPointF(local_x, local_y + 40)
        self._label = label
        self._win_info = {"_static": True}
        self._menu_mode = False
        self.setGeometry(geo)
        self.show()
        self._raise_above_layer8()
        self._timer.start()

    def dismiss(self) -> None:
        self._timer.stop()
        self._win_info = None
        self.hide()

    # ------------------------------------------------------------------
    # Internal

    def _position_on_screen(self) -> None:
        """Recompute tip position and place the overlay on the right screen."""
        if self._win_info is None:
            return
        bounds = self._win_info["kCGWindowBounds"]
        bx, by = bounds["X"], bounds["Y"]
        bw, bh = bounds["Width"], bounds["Height"]
        img_w, img_h = self._img_size
        box = self._box

        # Box center in screen points
        cx = bx + ((box["left"] + box["width"] / 2) / img_w) * bw
        cy = by + ((box["top"] + box["height"] / 2) / img_h) * bh

        screen = (QGuiApplication.screenAt(QPoint(int(cx), int(cy)))
                  or QGuiApplication.primaryScreen())
        geo = screen.geometry()
        self._screen_origin = geo.topLeft()
        self._arrow_tip = QPointF(cx - geo.x(), cy - geo.y())
        self.setGeometry(geo)

    def _position_menu_arrow(self) -> None:
        """Place tip at the menu window's nearer edge, tail 40pt outside."""
        if self._win_info is None:
            return
        bounds = self._win_info["kCGWindowBounds"]
        bx, by = bounds["X"], bounds["Y"]
        bw, bh = bounds["Width"], bounds["Height"]
        img_w, img_h = self._img_size
        box = self._box

        cx = bx + ((box["left"] + box["width"] / 2) / img_w) * bw
        cy = by + ((box["top"] + box["height"] / 2) / img_h) * bh

        screen = (QGuiApplication.screenAt(QPoint(int(cx), int(cy)))
                  or QGuiApplication.primaryScreen())
        geo = screen.geometry()
        self._screen_origin = geo.topLeft()

        space_left = bx - geo.x()
        space_right = (geo.x() + geo.width()) - (bx + bw)

        if space_left >= space_right:
            tip_x = bx - geo.x() - 4
            tail_x = tip_x - 40
        else:
            tip_x = bx + bw - geo.x() + 4
            tail_x = tip_x + 40

        tip_y = cy - geo.y()
        self._arrow_tip = QPointF(tip_x, tip_y)
        self._arrow_tail = QPointF(tail_x, tip_y)
        self.setGeometry(geo)

    def _follow(self) -> None:
        """Reposition overlay to match the current plugin window bounds.
        Hides only if the plugin window itself disappears."""
        if self._win_info is None:
            return

        if self._win_info.get("_static"):
            self._reorder_to_front()
            self.update()
            return

        if self._menu_mode:
            # Menu windows are layer 101 — not in find_all_logic_pro_windows (layers 0/3/8).
            # The MenuWatcher owns the menu lifecycle; just keep the arrow on top.
            self._reorder_to_front()
            self.update()
            return

        try:
            target_num = self._win_info.get("kCGWindowNumber")
            wins = find_all_logic_pro_windows()
            match = next((w for w in wins if w.get("kCGWindowNumber") == target_num), None)
            if match is None:
                self.hide()
                return
            self._win_info = match
        except Exception:
            return

        self._position_on_screen()
        if not self.isVisible():
            self.show()
        self._reorder_to_front()
        self.update()

    def _ns_window(self):
        """Return the backing NSWindow via pyobjc, or None on failure."""
        try:
            view = objc.objc_object(c_void_p=int(self.winId()))
            return view.window()
        except Exception:
            return None

    def _raise_above_layer8(self) -> None:
        win = self._ns_window()
        if win is None:
            print("[overlay] NSWindow raise failed: could not get NSWindow")
            return
        try:
            win.setLevel_(8)  # kCGModalPanelWindowLevel — above Logic's floating plugin (3)
            win.setHidesOnDeactivate_(False)
            win.setCollectionBehavior_(1 | 16)  # CanJoinAllSpaces | Stationary
            win.setIgnoresMouseEvents_(True)
        except Exception as e:
            print(f"[overlay] NSWindow raise failed: {e}")

    def _reorder_to_front(self) -> None:
        """Push to front of its window level every timer tick.

        orderFrontRegardless() is an active reorder (move to front now,
        regardless of which app is active) — distinct from setLevel_() which
        is a passive level-set that the window server can demote on activation.
        """
        win = self._ns_window()
        if win is not None:
            try:
                win.orderFrontRegardless()
            except Exception:
                pass

    def paintEvent(self, _) -> None:
        if self._arrow_tip is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        tip = self._arrow_tip
        tail = (self._arrow_tail if self._arrow_tail is not None
                else QPointF(tip.x(), tip.y() - 40))
        ang = math.atan2(tip.y() - tail.y(), tip.x() - tail.x())

        p.setPen(QPen(_BLUE, 3))
        p.drawLine(tail, tip)
        for da in (math.radians(150), math.radians(-150)):
            p.drawLine(tip, QPointF(tip.x() + 12 * math.cos(ang + da),
                                    tip.y() + 12 * math.sin(ang + da)))

        if self._label:
            from PySide6.QtWidgets import QApplication
            font = QApplication.font()
            font.setPointSize(11)
            p.setFont(font)
            fm = p.fontMetrics()
            cw = fm.horizontalAdvance(self._label) + 10
            ch = fm.height() + 4
            is_static = isinstance(self._win_info, dict) and self._win_info.get("_static")
            if is_static:
                # Upward arrow pointing at menu bar: label below the tail
                cx = tip.x() - cw / 2
                cy = tail.y() + 6
            elif self._menu_mode:
                # Horizontal arrow pointing at menu item: label to the right of the tip
                cx = tip.x() + 8
                cy = tip.y() - ch / 2
            else:
                # Default: label above midpoint of shaft
                cx = (tip.x() + tail.x()) / 2 - cw / 2
                cy = min(tip.y(), tail.y()) - ch - 4
            chip = QRectF(cx, cy, cw, ch)
            p.setPen(Qt.NoPen)
            p.setBrush(_BLUE)
            p.drawRoundedRect(chip, 4, 4)
            p.setPen(qcolor(WHITE))
            p.drawText(chip, Qt.AlignCenter, self._label)

        p.end()
