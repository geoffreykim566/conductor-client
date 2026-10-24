"""Small animations: widget fade-ins, window fades. All skipped when macOS
"Reduce motion" is on (System Settings > Accessibility > Display).

An animation is parented to its target, so it can't outlive it; a new
window fade stops the one still running on that window.
"""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect

try:
    import AppKit
except Exception:  # pragma: no cover - pyobjc missing outside macOS
    AppKit = None

FADE_MS = 180
WINDOW_FADE_MS = 150

_reduce: bool | None = None


def reduce_motion() -> bool:
    global _reduce
    if _reduce is None:
        try:
            _reduce = bool(AppKit.NSWorkspace.sharedWorkspace()
                           .accessibilityDisplayShouldReduceMotion())
        except Exception:
            _reduce = False
    return _reduce


def fade_in(widget, ms: int = FADE_MS) -> None:
    """Fade a child widget in. The opacity effect is removed at the end: a
    lingering effect re-renders the widget offscreen on every paint."""
    if reduce_motion() or widget.graphicsEffect() is not None:
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start(QPropertyAnimation.DeleteWhenStopped)


def fade_window_in(window) -> None:
    """Fade a top-level window in; call from its showEvent."""
    _fade(window, 0.0, 1.0)


def hide_faded(window, then=None) -> None:
    """Fade a top-level window out, then hide() it (and call `then`)."""
    def done():
        window.hide()
        window.setWindowOpacity(1.0)
        if then is not None:
            then()
    if reduce_motion() or not window.isVisible():
        done()
        return
    _fade(window, window.windowOpacity(), 0.0, done)


def _fade(window, start: float, end: float, done=None) -> None:
    running = getattr(window, "_fade_anim", None)
    if running is not None:
        running.stop()   # stop() doesn't emit finished, so its done() is dropped
        running.deleteLater()
        window._fade_anim = None
    if reduce_motion():
        window.setWindowOpacity(end)
        if done is not None:
            done()
        return
    window.setWindowOpacity(start)
    anim = QPropertyAnimation(window, b"windowOpacity", window)
    anim.setDuration(WINDOW_FADE_MS)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.OutCubic if end > start else QEasingCurve.InCubic)

    def finished():
        window._fade_anim = None
        anim.deleteLater()
        if done is not None:
            done()
    anim.finished.connect(finished)
    window._fade_anim = anim
    anim.start()
