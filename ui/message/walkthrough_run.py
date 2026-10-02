"""Run / revert lifecycle of a WalkthroughCard: executor and revert threads, interrupt tap, outcomes."""
import threading

from PySide6.QtCore import Qt

from core.automation import (
    ExecutorThread,
    RevertThread,
    WalkthroughInterruptTap,
    check_event_permission,
    wire_to_steps,
)
from ui.message.styles import STATUS_ERROR_STYLE, STATUS_INFO_STYLE


class WalkthroughRunMixin:
    """Mixed into WalkthroughCard; uses the card's widgets and view-state methods."""

    def enter(self) -> None:
        """Enter / the card's main button: Run in Ready, Revert in Done, Try
        again after a failed or stopped run or a failed Revert. During a run
        it does nothing (any real input already stops the run via the
        interrupt tap)."""
        if not self.isVisible():
            return
        state = getattr(self, "_state", "ready")
        if state in ("done", "revert_failed"):
            self.revert()
            return
        if state not in ("ready", "retry") or self._active:
            return
        self._active = True
        self._state = "running"
        self._hint.hide()
        self._button.hide()
        self._button2.hide()
        if not self._run_executor():
            self._active = False
            self._show_retry(None)   # the permission message is already showing

    def revert(self) -> None:
        if (getattr(self, "_state", None) not in ("done", "retry", "revert_failed")
                or not getattr(self, "_ledger", None)):
            return
        self._state = "reverting"
        self._button.setEnabled(False)
        self._button2.hide()
        self._hint.hide()
        self._status.setStyleSheet(STATUS_INFO_STYLE)
        self._status.setText("Reverting — hands off for a moment")
        self._status.show()
        worker = RevertThread(self._ledger, parent=self)
        worker.done.connect(self._on_reverted)
        self._workers.append(worker)
        worker.start()

    def _on_reverted(self, results) -> None:
        self._stop_threads()
        # Keep what didn't revert (by identity: a thread-level error reports a
        # stand-in entry, so everything not confirmed reverted stays).
        reverted = {id(r[0]) for r in results if r[1]}
        remaining = [e for e in self._ledger if id(e) not in reverted]
        self._ledger = remaining
        self._end_hint.hide()
        if not remaining:
            self._state = "reverted"
            self._button.hide()
            self._hint.hide()
            self._status.setStyleSheet(STATUS_INFO_STYLE)
            self._status.setText("Reverted")
        else:
            self._state = "revert_failed"
            failed = "; ".join(f"{r[0].get('label', '?')}: {r[2]}" for r in results if not r[1])
            self._status.setStyleSheet(STATUS_ERROR_STYLE)
            self._status.setText(f"Couldn't revert everything — {failed}")
            self._button.setText("Try again")
            self._button.setEnabled(True)
            self._button.show()
            self._hint.setText("Press ↵ to try reverting again")
            self._hint.show()
        self._status.show()

    def _run_executor(self) -> bool:
        """Start a run from `_resume`. False if it couldn't start (a
        permission is missing; the message is already on the card)."""
        if not check_event_permission():
            self._show_permission_needed()
            self._active = False
            return False
        translated = wire_to_steps(self._steps)
        if not translated:
            self._show_permission_needed()
            self._active = False
            return False

        interrupt_tap = WalkthroughInterruptTap(parent=self)
        if not interrupt_tap.arm():
            self._show_permission_needed(
                "Needs Input Monitoring permission — System Settings → Privacy & "
                "Security → Input Monitoring, then try again."
            )
            self._active = False
            return False

        self._status.setStyleSheet(STATUS_INFO_STYLE)
        self._status.setText("Running — hands off for a moment")
        self._status.show()
        self._end_hint.show()

        stop_event = threading.Event()
        executor = ExecutorThread(translated, stop_event=stop_event, parent=self,
                                  start_at=self._resume)
        executor.step_started.connect(self._on_step_started)
        executor.finished.connect(self._on_finished)
        executor.failed.connect(self._on_failed)
        self._executor = executor
        self._workers.append(executor)  # keep-alive: stop() doesn't exit the
        # thread immediately, so the last strong ref can't drop until it does

        # Instant + non-blocking: unblocks the in-flight action within about
        # one keystroke. The UI teardown is queued rather than run inline —
        # _end() -> _teardown() blocks up to 2s waiting for the thread
        # to exit, and doing that synchronously inside the tap callback risks
        # macOS disabling the tap for taking too long to return.
        interrupt_tap.triggered.connect(stop_event.set)
        interrupt_tap.triggered.connect(self._on_stopped, Qt.ConnectionType.QueuedConnection)
        self._interrupt_tap = interrupt_tap

        executor.start()
        return True

    def _on_step_started(self, idx: int) -> None:
        print(f"[wt] executor step_started idx={idx}")
        self._highlight_step(idx)

    def _on_finished(self, ledger=None) -> None:
        print(f"[wt] executor finished; ledger={len(ledger or [])} entries")
        if self._state != "running":
            return
        self._teardown()
        # a Try again's changes join the earlier attempts'; Revert undoes all
        # of them newest first, so a value changed twice ends at its original
        combined = self._ledger + list(ledger or [])
        if combined:
            self._show_done(combined, "Done")
        else:
            self._state = "finished"
            self.hide()

    def _collect_attempt(self) -> None:
        """Fold a stopped/failed attempt into the card: its changes join the
        ledger, and the next Try again starts where it says."""
        ex = self._executor
        self._teardown()   # waits for the thread, so its ledger is final
        if ex is not None:
            self._ledger = self._ledger + list(ex.ledger or [])
            self._resume = ex.resume_at

    def _on_failed(self, idx: int, msg: str) -> None:
        print(f"[wt] executor failed at step {idx}: {msg}")
        if self._state != "running":
            return
        self._collect_attempt()
        if idx >= 0:
            self._mark_step_failed(idx)
            note = f"Couldn't finish step {idx + 1}."
        else:
            note = f"Couldn't start — {msg}."   # activation: the reason is the user's fix
        if self._ledger:
            note += " Earlier steps can be reverted."
        # Card stays visible so the step list remains as a manual guide.
        self._show_retry(note)

    def _on_stopped(self) -> None:
        """The user pressed a key / clicked / scrolled during the run."""
        if self._state != "running":
            return   # the tap fired after the run had already ended
        print("[wt] run stopped by user input")
        self._collect_attempt()
        try:
            from ui.overlay_window import instance as _overlay
            _overlay().dismiss()
        except Exception:
            pass
        self._highlight_step(-1)
        self._show_retry("Stopped.", error=False)

    def _stop_threads(self) -> None:
        """Synchronously stop and wait for any running walkthrough thread.

        Qt6 aborts the whole process if a QThread is destroyed while still
        running (see README "QThread teardown"). .stop() alone only sets a
        flag, so anything that can tear down this widget (or the app) must
        wait for the thread to actually exit first.

        """
        for w in getattr(self, "_workers", []):
            if w.isRunning():
                if hasattr(w, "stop"):
                    w.stop()
                w.wait(2000)
        self._workers = []

    def _teardown(self) -> None:
        self._stop_threads()
        self._executor = None
        self._active = False
        if getattr(self, "_interrupt_tap", None) is not None:
            self._interrupt_tap.disarm()
            self._interrupt_tap = None

    def _end(self) -> None:
        """External stop (app quit, chat cleared) — tears down and hides the card."""
        self._teardown()
        try:
            from ui.overlay_window import instance as _overlay
            _overlay().dismiss()
        except Exception:
            pass
        self.hide()

    def force_end(self) -> None:
        """External safety hook: stop an active run (and hide the card) before
        the card or the app is torn down. A no-op when nothing is running."""
        if not getattr(self, "_active", False):
            return
        self._active = False
        self._end()
