"""Native glass behind a frameless, translucent Qt window (README "Glass backdrop").

macOS 26+: Liquid Glass (NSGlassEffectView shapes in a plain NSView; not an
NSGlassEffectContainerView, see README "Glass backdrop").
macOS 12-25: NSVisualEffectView, the dark HUD blur (no refraction).
Neither, or anything failing: mode() is "" and windows paint their old panel.
CONDUCTOR_GLASS=off|blur forces a lower tier (for checking the fallbacks).
"""
import os

from PySide6.QtCore import QEvent, QObject, QRect, QTimer

try:
    import AppKit
    import objc
except Exception:  # pragma: no cover - pyobjc missing outside macOS
    AppKit = None

_ATTACH_TRIES = 5

_mode: str | None = None


def mode() -> str:
    """'glass', 'blur' or '' (no native backdrop), decided once per run."""
    global _mode
    if _mode is None:
        forced = os.environ.get("CONDUCTOR_GLASS", "").lower()
        if AppKit is None or forced == "off":
            _mode = ""
        elif forced != "blur" and hasattr(AppKit, "NSGlassEffectView"):
            _mode = "glass"
        elif hasattr(AppKit, "NSVisualEffectView"):
            _mode = "blur"
        else:
            _mode = ""
    return _mode


class GlassBackdrop(QObject):
    """Native glass shapes kept under a top-level widget's own drawing.

    `shapes()` returns [(QRect in window coordinates, corner radius)]. The
    backdrop re-reads it when the window shows or resizes, and when a widget
    passed to watch() moves, resizes, shows or hides.

    `roots` are the widgets that paint the panel when there's no glass: they
    get glass="true" (ui/style.py drops their fill) from the start, so the
    first frame is already right, and lose it again if attaching fails.
    `active` says whether glass is attached, for windows that paint in code.
    """

    def __init__(self, window, shapes, roots=()) -> None:
        super().__init__(window)
        self._window = window
        self._shapes = shapes
        self._roots = list(roots)
        self._holder = None     # added to the window's frame view, under Qt's view; holds the shapes
        self._views: list = []
        self._ns_window = None
        self.active = bool(mode())
        if self.active:
            window.installEventFilter(self)
        self._mark_roots()

    def _mark_roots(self) -> None:
        for w in self._roots:
            if w.property("glass") != self.active:
                w.setProperty("glass", self.active)
                w.style().unpolish(w)
                w.style().polish(w)

    def watch(self, *widgets) -> None:
        for w in widgets:
            w.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        t = event.type()
        if obj is self._window:
            if t in (QEvent.Type.Show, QEvent.Type.WinIdChange):
                self._attach()
            elif t == QEvent.Type.Resize:
                self.sync()
        elif t in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.Hide):
            self.sync()
        return False

    def _attach(self, tries: int = _ATTACH_TRIES) -> None:
        """Put the holder view under Qt's view, in the window's frame view.
        Qt's view stays the window's contentView: Qt's Cocoa backend moves and
        resizes the NSWindow itself only while its view is the contentView.
        A first show can arrive before Qt has made the NSWindow; then this
        retries on the next event-loop turns."""
        if not self.active:
            return
        try:
            qview = objc.objc_object(c_void_p=int(self._window.winId()))
            ns_window = qview.window()
            frame_view = qview.superview() if ns_window is not None else None
            if frame_view is None:
                if tries <= 0:
                    raise RuntimeError("no native window")
                QTimer.singleShot(0, lambda: self._attach(tries - 1))
                return
            if self._holder is not None and self._holder.superview() == frame_view:
                self.sync()
                return
            ns_window.setOpaque_(False)
            ns_window.setBackgroundColor_(AppKit.NSColor.clearColor())
            # The window shadow traced the shapes with a heavy dark outline and
            # greyed the glass; the glass reads as a layer without it.
            ns_window.setHasShadow_(False)
            ns_window.setAppearance_(
                AppKit.NSAppearance.appearanceNamed_(AppKit.NSAppearanceNameDarkAqua))
            holder = AppKit.NSView.alloc().initWithFrame_(qview.frame())
            holder.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
            frame_view.addSubview_positioned_relativeTo_(holder, AppKit.NSWindowBelow, qview)
            self._holder, self._ns_window = holder, ns_window
            self._views = []
            self.sync()
        except Exception as e:  # back to the painted panel
            print(f"[glass] attach failed: {e}", flush=True)
            self.active = False
            self._mark_roots()
            self._window.update()

    def _new_view(self):
        if mode() == "glass":
            view = AppKit.NSGlassEffectView.alloc().initWithFrame_(((0, 0), (1, 1)))
            # No tintColor: macOS applies it only while the window is key, and
            # this window rarely is (Logic is). Qt paints the dark wash instead
            # (theme GLASS_WASH), which holds either way.
            view.setStyle_(AppKit.NSGlassEffectViewStyleRegular)
            # Clipped to its rounded shape (cornerRadius in sync() sets the
            # layer's too): while the window is key the glass casts a shadow
            # past its shape, which the window edge cut into a dark rectangle.
            view.setWantsLayer_(True)
            view.layer().setMasksToBounds_(True)
        else:
            view = AppKit.NSVisualEffectView.alloc().initWithFrame_(((0, 0), (1, 1)))
            view.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
            view.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
            view.setState_(AppKit.NSVisualEffectStateActive)
            view.setWantsLayer_(True)
            view.layer().setMasksToBounds_(True)
        self._holder.addSubview_(view)
        return view

    def sync(self) -> None:
        if not self.active or self._holder is None:
            return
        try:
            shapes = [(r, rad) for r, rad in self._shapes() if r.width() > 0 and r.height() > 0]
            while len(self._views) < len(shapes):
                self._views.append(self._new_view())
            # Sized from Qt, not from the native views: on a Qt resize the
            # NSWindow (and the autoresized holder) can still have the old size.
            height = self._window.height()
            for i, view in enumerate(self._views):
                if i >= len(shapes):
                    view.setHidden_(True)
                    continue
                rect, radius = shapes[i]
                view.setHidden_(False)
                # Cocoa's y runs up from the bottom; Qt's runs down from the top.
                view.setFrame_(((rect.x(), height - rect.y() - rect.height()),
                                (rect.width(), rect.height())))
                if mode() == "glass":
                    view.setCornerRadius_(radius)
                view.layer().setCornerRadius_(radius)
        except Exception as e:
            print(f"[glass] sync failed: {e}", flush=True)


def full_rect(widget, radius: float):
    """shapes() for a window whose whole rect is one rounded panel."""
    return lambda: [(QRect(0, 0, widget.width(), widget.height()), radius)]
