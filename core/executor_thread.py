"""QThread wrapper around core.executor.run_steps — the executor's UI-facing thread.

Mirrors core.walkthrough_poller.WalkthroughPoller's stop()+wait() teardown discipline
(Qt6 aborts the process if a QThread is destroyed while still running) but drives a
one-shot act->verify run instead of a continuous poll: step_started fires right before
each step's action, finished/failed report the terminal outcome.

Stop is preemptive: a shared threading.Event (stop_event) is threaded into
run_steps(), which checks it at fine granularity inside the low-level
posting functions (per character, per menu hop), not just once between
whole steps — see core.interrupt_tap.WalkthroughInterruptTap, which sets it
the instant any real (non-Conductor) key/click/scroll lands during a run.
"""
import threading
import time

from PySide6.QtCore import QThread, Signal

from core.executor import MENU_SETTLE_S, StepAbort, activate_logic, run_steps


class ExecutorThread(QThread):
    """Runs a translated step list end to end; reports progress as it goes.

    step_started(idx)  — about to act on step `idx` (0-based, for card highlighting).
    finished            — every step completed and verified.
    failed(idx, msg)    — step `idx` aborted; msg is the StepAbort text (activation
                           failure reports as step -1, before any step ran).
    """
    step_started = Signal(int)
    finished = Signal()
    failed = Signal(int, str)

    def __init__(self, steps: list[dict], stop_event: threading.Event | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self._steps = steps
        self._stop_flag = False
        self._stop_event = stop_event if stop_event is not None else threading.Event()

    def stop(self) -> None:
        self._stop_flag = True
        self._stop_event.set()

    def run(self) -> None:
        # Blocking (up to 3s) — deliberately run on this background thread,
        # not the Qt main thread, so activation confirmation never freezes
        # the UI. Confirming Logic is actually frontmost here (rather than a
        # fire-and-forget activate call before starting this thread) avoids
        # a race against the first step's own frontmost guard.
        if not activate_logic():
            self.failed.emit(-1, "couldn't bring Logic Pro to the front")
            return
        # NSWorkspace reports Logic frontmost before the system menu bar has
        # actually redrawn — the first capture otherwise races that redraw
        # (see executor.py's MENU_SETTLE_S, used after every later menu-bar
        # interaction but not before this first one).
        time.sleep(MENU_SETTLE_S)
        for idx, step in enumerate(self._steps):
            if self._stop_flag or self._stop_event.is_set():
                return
            self.step_started.emit(idx)
            log = lambda msg, i=idx: print(f"[executor_thread] step {i}: {msg}")
            try:
                run_steps([step], log=log, stop_event=self._stop_event)
            except StepAbort as exc:
                self.failed.emit(idx, str(exc))
                return
            except Exception as exc:
                self.failed.emit(idx, f"{type(exc).__name__}: {exc}")
                return
            if self._stop_flag or self._stop_event.is_set():
                return
        self.finished.emit()
