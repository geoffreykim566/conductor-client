"""QThreads that run a step list (ExecutorThread) or a revert (RevertThread) off the UI thread.

Stop is preemptive: a shared threading.Event (stop_event) is threaded into
run_steps(), which checks it at fine granularity inside the low-level
posting functions (per character, per menu hop), not just between whole
steps -- interrupt_tap.WalkthroughInterruptTap sets it the instant any real
(non-Conductor) key/click/scroll lands during a run. Owners must stop() and
wait() before destroying these: Qt6 aborts the process if a QThread is
destroyed while running.
"""
import threading
import time

from PySide6.QtCore import QThread, Signal

from core.automation.errors import StepAbort
from core.automation.logic_focus import activate_logic, wait_logic_on_screen
from core.automation.revert import revert
from core.automation.runner import run_steps
from core.automation.timing import MENU_SETTLE_S


class ExecutorThread(QThread):
    """Runs a translated step list end to end; reports progress as it goes.

    step_started(idx)  — about to act on step `idx` (0-based, for card highlighting).
    finished(ledger)    — every step completed and verified; `ledger` is the list of
                           revert entries (see revert.py), possibly empty.
    failed(idx, msg)    — step `idx` aborted; msg is the StepAbort text (activation
                           failure reports as step -1, before any step ran). The
                           partial ledger is available as `.ledger` for a revert.

    `start_at` skips the steps before it (a Try again). `.resume_at` is where a
    Try again after this run should start: just past the last step that changed
    something, since every later step re-reads Logic's state, while repeating a
    change isn't always harmless ("one step larger", "add a second copy").
    """
    step_started = Signal(int)
    finished = Signal(object)
    failed = Signal(int, str)

    def __init__(self, steps: list[dict], stop_event: threading.Event | None = None,
                 parent=None, start_at: int = 0) -> None:
        super().__init__(parent)
        self._steps = steps
        self._stop_flag = False
        self._stop_event = stop_event if stop_event is not None else threading.Event()
        self.ledger: list[dict] = []
        self.resume_at = start_at

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
        # Frontmost isn't on screen: from another desktop the windows are still
        # sliding in, and a first capture that sees nothing misreads the screen.
        if not wait_logic_on_screen():
            self.failed.emit(-1, "Logic's project window isn't on this desktop — bring it "
                                 "to this desktop and try again")
            return
        # NSWorkspace reports Logic frontmost before the system menu bar has
        # actually redrawn — the first capture otherwise races that redraw
        # (timing.MENU_SETTLE_S, used after every later menu-bar interaction).
        time.sleep(MENU_SETTLE_S)
        for idx, step in enumerate(self._steps):
            if idx < self.resume_at:
                continue
            if self._stop_flag or self._stop_event.is_set():
                return
            self.step_started.emit(idx)
            log = lambda msg, i=idx: print(f"[executor_thread] step {i}: {msg}")
            try:
                changed = run_steps([step], log=log, stop_event=self._stop_event) or []
                if changed:
                    self.ledger.extend(changed)
                    self.resume_at = idx + 1
            except StepAbort as exc:
                self.failed.emit(idx, str(exc))
                return
            except Exception as exc:
                self.failed.emit(idx, f"{type(exc).__name__}: {exc}")
                return
            if self._stop_flag or self._stop_event.is_set():
                return
        self.finished.emit(list(self.ledger))


class RevertThread(QThread):
    """Applies a run's ledger in reverse (revert.revert) off the UI thread.

    done(results) — list of (entry, ok, message); never raises.
    """
    done = Signal(object)

    def __init__(self, ledger: list[dict], parent=None) -> None:
        super().__init__(parent)
        self._ledger = list(ledger)

    def stop(self) -> None:  # symmetry with ExecutorThread for the card's _stop_threads
        pass

    def run(self) -> None:
        results = []
        try:
            if activate_logic() and wait_logic_on_screen():
                time.sleep(MENU_SETTLE_S)
            results = revert(self._ledger, log=lambda m: print(f"[revert_thread] {m}"))
        except Exception as exc:  # noqa: BLE001
            results = [({"label": "revert"}, False, f"{type(exc).__name__}: {exc}")]
        self.done.emit(results)
