"""VoiceController: the mic pill's behaviour. Starts and stops the recorder, sends each phrase to
the server in order, puts the text in at the cursor, and keeps the daily limit's state.
How the pieces fit: README "Voice input"."""
import datetime as dt

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QDesktopServices

from core.net.voice import TranscribeWorker
from core.state import prefs
from core.voice.recorder import VoiceRecorder

MAX_RECORDING_S = 60
_COUNTDOWN_S = 10
_MIC_PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"

NOTES = {
    "denied": "Microphone access is off. Click the mic to allow it.",
    "no_input": "No microphone found.",
    "open_failed": "Couldn't use that microphone.",
    "silent_mic": "No sound from that microphone. Try another one.",
    "offline": "Couldn't reach Conductor.",
    "failed": "Couldn't make that into text. Try again.",
}


def resets_text(iso: str) -> str:
    """'resets at 12:00 AM' in local time; '' if unknown."""
    try:
        when = dt.datetime.fromisoformat(iso).astimezone()
    except (TypeError, ValueError):
        return ""
    return "resets at " + when.strftime("%-I:%M %p")


class VoiceController(QObject):
    """`insert(text)` puts text at the cursor; `context()` is the text already in the box;
    `note(text)` shows a message ('' clears it); `countdown(text)` the last seconds ('' hides it)."""

    def __init__(self, pill, insert, context, note, countdown, parent=None) -> None:
        super().__init__(parent)
        self._pill, self._insert, self._context = pill, insert, context
        self._note, self._countdown = note, countdown
        self._rec = VoiceRecorder(self)
        self._rec.started.connect(lambda: self._set_listening(True))
        self._rec.phrase.connect(self._on_phrase)
        self._rec.elapsed.connect(self._on_elapsed)
        self._rec.silent_mic.connect(lambda: self._note(NOTES["silent_mic"]))
        self._rec.stopped.connect(lambda _reason: self._set_listening(False))
        self._rec.failed.connect(self._on_failed)
        pill.mic_clicked.connect(self.toggle)
        pill.device_picked.connect(lambda: self._note(""))

        self._queue: list[bytes] = []
        self._worker: TranscribeWorker | None = None
        self._generation = 0        # bumped on cancel: results from before it are dropped
        self._seconds_left: int | None = None
        self._resets_at = ""
        self._denied = False
        self._cap = MAX_RECORDING_S
        self._dropping = False      # during cancel(): the stop's flushed phrase is never sent

    # --- the daily limit ---
    def set_seconds_left(self, seconds: int, resets_at: str = "") -> None:
        self._seconds_left = max(seconds, 0)
        if resets_at:
            self._resets_at = resets_at
        self._pill.set_blocked(self._seconds_left == 0, self._limit_text())

    def _limit_text(self) -> str:
        when = resets_text(self._resets_at)
        return f"Voice limit reached for today{', ' + when if when else ''}."

    # --- start / stop ---
    def toggle(self) -> None:
        if self._rec.is_running():
            self._rec.stop()
            return
        if self._pill.is_busy():
            return   # still turning the last recording into text
        if self._denied:
            QDesktopServices.openUrl(QUrl(_MIC_PANE))
            return
        if self._seconds_left == 0:
            self._note(self._limit_text())
            return
        self._note("")
        left = self._seconds_left if self._seconds_left is not None else MAX_RECORDING_S
        self._cap = max(1, min(MAX_RECORDING_S, left))
        self._rec.start(prefs.mic_device(), self._cap)

    def stop(self) -> None:
        """Stop listening; the phrase in progress is still sent (typing in the box)."""
        if self._rec.is_running():
            self._rec.stop()

    def cancel(self) -> None:
        """Stop and drop anything not yet in the box (the message was sent)."""
        self._generation += 1
        self._queue.clear()
        self._dropping = True
        try:
            if self._rec.is_running():
                self._rec.stop()
        finally:
            self._dropping = False
        self._pill.set_busy(False)   # a result still in flight is dropped, not waited for

    def shutdown(self) -> None:
        self.cancel()
        if self._worker is not None:
            self._worker.wait(3000)

    def _set_listening(self, on: bool) -> None:
        self._pill.set_listening(on)
        self._countdown("")
        self._update_busy()
        if not on:
            self._pill.set_blocked(self._seconds_left == 0, self._limit_text())

    def _on_elapsed(self, secs: float) -> None:
        left = int(self._cap - secs)
        if left <= _COUNTDOWN_S:
            self._countdown(f"0:{max(left, 0):02d}")

    def _on_failed(self, reason: str) -> None:
        self._denied = reason == "denied"
        self._set_listening(False)
        self._note(NOTES.get(reason, NOTES["failed"]))

    # --- phrases, in order ---
    def _on_phrase(self, wav: bytes) -> None:
        if self._dropping:
            return
        self._queue.append(wav)
        self._next()

    def _next(self) -> None:
        if self._worker is not None or not self._queue:
            return
        wav = self._queue.pop(0)
        gen = self._generation
        w = TranscribeWorker(wav, self._context(), self)
        w.done.connect(lambda text, left, resets, g=gen: self._on_text(g, text, left, resets))
        w.limit.connect(lambda resets, g=gen: self._on_limit(g, resets))
        w.failed.connect(lambda kind, code, g=gen: self._on_error(g, kind))
        w.finished.connect(self._on_worker_done)
        self._worker = w
        w.start()

    def _on_worker_done(self) -> None:
        w, self._worker = self._worker, None
        if w is not None:
            w.deleteLater()
        self._next()
        self._update_busy()

    def _update_busy(self) -> None:
        """Spinner on while stopped with phrases still being turned into text."""
        waiting = self._worker is not None or bool(self._queue)
        self._pill.set_busy(waiting and not self._rec.is_running())

    def _on_text(self, gen: int, text: str, left: int, resets_at: str) -> None:
        if left >= 0:
            self.set_seconds_left(left, resets_at)
        if gen == self._generation and text.strip():
            self._insert(text.strip())
        if self._seconds_left == 0:
            self._rec.stop()

    def _on_limit(self, gen: int, resets_at: str) -> None:
        self._queue.clear()
        self.set_seconds_left(0, resets_at)
        self._rec.stop()
        self._note(self._limit_text())

    def _on_error(self, gen: int, kind: str) -> None:
        if gen == self._generation:
            self._note(NOTES["offline"] if kind == "offline" else NOTES["failed"])
