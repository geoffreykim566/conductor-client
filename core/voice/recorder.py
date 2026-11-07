"""VoiceRecorder: asks for the microphone, records the chosen input as 16 kHz mono PCM, and runs
it through PhraseDetector. Emits finished phrases as WAV bytes. Lives on the UI thread (Qt's
audio input delivers on the event loop; nothing here blocks)."""
import io
import wave

from PySide6.QtCore import QCoreApplication, QMicrophonePermission, QObject, Qt, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QtAudio

from core.voice import devices
from core.voice.detector import RATE, PhraseDetector


def to_wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return buf.getvalue()


class VoiceRecorder(QObject):
    """Signals:
        started()            -- the mic is open and listening
        phrase(bytes)        -- one finished phrase, as a WAV
        elapsed(float)       -- seconds recorded so far (for the countdown)
        silent_mic()         -- the input sends only zeros (closed lid, input in use elsewhere)
        stopped(str)         -- "idle" | "cap" | "manual"; any last phrase was emitted first
        failed(str)          -- "denied" | "no_input" | "open_failed"; nothing was recorded
    """

    started = Signal()
    phrase = Signal(bytes)
    elapsed = Signal(float)
    silent_mic = Signal()
    stopped = Signal(str)
    failed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._source: QAudioSource | None = None
        self._io = None
        self._det: PhraseDetector | None = None
        self._pending: tuple[str | None, float] | None = None
        self._last_elapsed = -1.0

    def is_running(self) -> bool:
        return self._source is not None or self._pending is not None

    def start(self, device_id: str | None, max_seconds: float) -> None:
        if self.is_running():
            return
        self._pending = (device_id, max_seconds)
        app = QCoreApplication.instance()
        perm = QMicrophonePermission()
        status = app.checkPermission(perm)
        if status == Qt.PermissionStatus.Granted:
            self._open()
        elif status == Qt.PermissionStatus.Undetermined:
            app.requestPermission(perm, self, self._on_permission)   # macOS shows its prompt
        else:
            self._fail("denied")

    def stop(self) -> None:
        """Manual stop: the phrase in progress is sent, then stopped("manual")."""
        if self._pending is not None and self._source is None:
            self._pending = None   # still waiting on the permission prompt
            return
        self._finish("manual")

    def _on_permission(self, perm) -> None:
        if self._pending is None:
            return
        if QCoreApplication.instance().checkPermission(perm) == Qt.PermissionStatus.Granted:
            self._open()
        else:
            self._fail("denied")

    def _open(self) -> None:
        device_id, max_seconds = self._pending
        self._pending = None
        dev = devices.resolve(device_id)
        if dev is None:
            self._fail("no_input")
            return
        fmt = QAudioFormat()
        fmt.setSampleRate(RATE)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.Int16)
        self._source = QAudioSource(dev, fmt, self)
        self._io = self._source.start()
        if self._io is None or self._source.error() != QtAudio.Error.NoError:
            self._source.deleteLater()
            self._source = self._io = None
            self._fail("open_failed")
            return
        self._det = PhraseDetector(max_seconds)
        self._last_elapsed = -1.0
        self._io.readyRead.connect(self._on_audio)
        self.started.emit()

    def _on_audio(self) -> None:
        if self._io is None or self._det is None:
            return
        ev = self._det.feed(bytes(self._io.readAll()))
        for pcm in ev.phrases:
            self.phrase.emit(to_wav(pcm))
        if ev.silent_mic:
            self.silent_mic.emit()
        secs = self._det.seconds
        if int(secs) != int(self._last_elapsed):
            self._last_elapsed = secs
            self.elapsed.emit(secs)
        if ev.stop:
            self._finish(ev.stop, flush=False)

    def _finish(self, reason: str, flush: bool = True) -> None:
        if self._source is None:
            return
        source, det = self._source, self._det
        self._source = self._io = self._det = None
        source.stop()
        source.deleteLater()
        if flush and det is not None:
            for pcm in det.flush():
                self.phrase.emit(to_wav(pcm))
        self.stopped.emit(reason)

    def _fail(self, reason: str) -> None:
        self._pending = None
        self.failed.emit(reason)
