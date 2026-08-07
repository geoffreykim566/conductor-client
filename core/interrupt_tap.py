"""Preemptive any-key/click/scroll interrupt for an active walkthrough.

A blocking CGEventTap over the current session: events Conductor itself
posted (tagged with core.executor.SYNTHETIC_EVENT_TAG — every CGEventPost
call in core.executor sets this) pass through untouched; anything untagged
is real user input, so it's swallowed (never reaches Logic Pro) and
`triggered` fires. Mouse-moved is not watched (desk bumps shouldn't abort a
run). This replaces the old listen-only Shift+Escape-only global monitor
(core.global_hotkey, deleted) on both axes: it can actually consume the
event, and it reacts to any real input, not one specific key combo.

Requires Input Monitoring — already a mandatory onboarding gate
(ui.setup_screen.has_input_monitoring_permission()) before any walkthrough
can run, so this needs no new permission screen. If CGEventTapCreate still
fails at runtime (e.g. permission revoked after onboarding), arm() returns
False and the caller refuses to start the walkthrough, same as the existing
check_event_permission() gate — no degraded fallback mode.
"""
import Quartz
from PySide6.QtCore import QObject, Signal

from core.executor import SYNTHETIC_EVENT_TAG

_WATCHED_TYPES = (
    Quartz.kCGEventKeyDown,
    Quartz.kCGEventLeftMouseDown,
    Quartz.kCGEventRightMouseDown,
    Quartz.kCGEventOtherMouseDown,
    Quartz.kCGEventScrollWheel,
)


class WalkthroughInterruptTap(QObject):
    """Watches for any real (untagged) key/click/scroll system-wide while armed.

    Must be armed on the Qt main thread — the tap's run-loop source is added
    to CFRunLoopGetCurrent(), which is the same run loop Qt's own Cocoa event
    dispatcher already services on that thread, so no manual pumping needed.
    """
    triggered = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._tap = None
        self._source = None

    def arm(self) -> bool:
        if self._tap is not None:
            return True
        mask = 0
        for t in _WATCHED_TYPES:
            mask |= Quartz.CGEventMaskBit(t)
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap, Quartz.kCGHeadInsertEventTap,
            0, mask, self._callback, None)
        if tap is None:
            return False
        self._tap = tap
        self._source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(), self._source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)
        return True

    def _callback(self, proxy, event_type, event, refcon):
        if event_type in (Quartz.kCGEventTapDisabledByTimeout,
                          Quartz.kCGEventTapDisabledByUserInput):
            Quartz.CGEventTapEnable(self._tap, True)
            return event
        tag = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGEventSourceUserData)
        if tag == SYNTHETIC_EVENT_TAG:
            return event
        print(f"[interrupt_tap] real input during walkthrough (type={event_type}) — aborting")
        self.triggered.emit()
        return None  # swallow — never reaches Logic Pro

    def disarm(self) -> None:
        if self._tap is None:
            return
        Quartz.CGEventTapEnable(self._tap, False)
        Quartz.CFRunLoopRemoveSource(
            Quartz.CFRunLoopGetCurrent(), self._source, Quartz.kCFRunLoopCommonModes)
        self._tap = None
        self._source = None
