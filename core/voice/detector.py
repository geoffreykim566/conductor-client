"""Pause detection on 16 kHz mono 16-bit PCM: cuts speech into phrases, drops the silence, and
says when to stop. Loudness against a running noise floor, no speech model. Why: README.md."""
import math
import struct
from dataclasses import dataclass, field

RATE = 16000
FRAME_MS = 30
FRAME_BYTES = RATE * FRAME_MS // 1000 * 2

MARGIN_DB = 10.0          # this far above the noise floor counts as speech
MIN_SPEECH_DB = -60.0     # and never quieter than this
FLOOR_WINDOW = 100        # frames (~3 s) the floor is taken from
FLOOR_PERCENTILE = 0.2
FLOOR_RISE_DB = 0.05      # per frame: the floor rises slowly, so a long sentence can't lift it to the voice
WARMUP_FRAMES = 10        # no speech decisions until the floor has this many frames
PAUSE_MS = 700            # a pause this long ends a phrase
TAIL_MS = 200             # of that pause, kept at the end of the phrase
PREROLL_MS = 240          # kept from just before speech starts
MIN_SPEECH_MS = 400       # a phrase with less speech than this is a noise, not sent
IDLE_STOP_S = 10.0        # no speech this long after the first speech: stop
SILENT_MIC_S = 1.5        # only digital zeros this long: the mic sends no sound
ZERO_DB = -119.0


def dbfs(frame: bytes) -> float:
    n = len(frame) // 2
    if not n:
        return -120.0
    samples = struct.unpack(f"<{n}h", frame[: n * 2])
    rms = math.sqrt(sum(s * s for s in samples) / n)
    return 20 * math.log10(rms / 32768) if rms > 0 else -120.0


@dataclass
class Events:
    """What one feed() produced."""
    phrases: list[bytes] = field(default_factory=list)
    stop: str | None = None        # "idle" | "cap" | None
    silent_mic: bool = False       # first time the mic is found sending only zeros
    level: float | None = None     # the last frame's dBFS


class PhraseDetector:
    """Feed raw PCM as it arrives; get back finished phrases and stop reasons.
    `max_seconds` is the recording cap (the 1-minute cap, or less near the daily limit)."""

    def __init__(self, max_seconds: float = 60.0) -> None:
        self.max_frames = int(max_seconds * 1000 / FRAME_MS)
        self._buf = b""
        self._recent: list[float] = []
        self.floor: float | None = None
        self._preroll: list[bytes] = []
        self._phrase: list[bytes] = []
        self._in_speech = False
        self._speech_ms = 0
        self._silent_ms = 0
        self.frames = 0
        self.heard = False
        self._since_speech_ms = 0
        self._zero_ms = 0
        self._warned_silent = False

    @property
    def seconds(self) -> float:
        return self.frames * FRAME_MS / 1000

    def feed(self, pcm: bytes) -> Events:
        ev = Events()
        self._buf += pcm
        while len(self._buf) >= FRAME_BYTES and ev.stop is None:
            frame, self._buf = self._buf[:FRAME_BYTES], self._buf[FRAME_BYTES:]
            self._frame(frame, ev)
        return ev

    def flush(self) -> list[bytes]:
        """The phrase in progress, if it's long enough (on a manual stop)."""
        if not self._in_speech:
            return []
        self._silent_ms = 0
        out = self._end_phrase(trim=False)
        return [out] if out else []

    def _frame(self, frame: bytes, ev: Events) -> None:
        self.frames += 1
        db = dbfs(frame)
        ev.level = db
        if db <= ZERO_DB:
            self._zero_ms += FRAME_MS
            if not self.heard and not self._warned_silent and self._zero_ms >= SILENT_MIC_S * 1000 \
                    and not self._recent:
                self._warned_silent = True
                ev.silent_mic = True
        else:
            self._update_floor(db)
        speech = (db > ZERO_DB and len(self._recent) >= WARMUP_FRAMES
                  and db > max(self.floor + MARGIN_DB, MIN_SPEECH_DB))

        if speech:
            self.heard = True
            self._since_speech_ms = 0
            if not self._in_speech:
                self._in_speech = True
                self._phrase = list(self._preroll)
                self._speech_ms = 0
            self._phrase.append(frame)
            self._speech_ms += FRAME_MS
            self._silent_ms = 0
        else:
            self._since_speech_ms += FRAME_MS
            if self._in_speech:
                self._phrase.append(frame)
                self._silent_ms += FRAME_MS
                if self._silent_ms >= PAUSE_MS:
                    out = self._end_phrase(trim=True)
                    if out:
                        ev.phrases.append(out)
        self._preroll = (self._preroll + [frame])[-(PREROLL_MS // FRAME_MS):]

        if self.frames >= self.max_frames:
            ev.phrases.extend(self.flush())
            ev.stop = "cap"
        elif self.heard and not self._in_speech and self._since_speech_ms >= IDLE_STOP_S * 1000:
            ev.stop = "idle"

    def _update_floor(self, db: float) -> None:
        self._recent = (self._recent + [db])[-FLOOR_WINDOW:]
        target = sorted(self._recent)[int(len(self._recent) * FLOOR_PERCENTILE)]
        if self.floor is None or target < self.floor:
            self.floor = target
        else:
            self.floor = min(target, self.floor + FLOOR_RISE_DB)

    def _end_phrase(self, trim: bool) -> bytes | None:
        self._in_speech = False
        frames = self._phrase
        self._phrase = []
        if self._speech_ms < MIN_SPEECH_MS:
            return None
        if trim:
            drop = (self._silent_ms - TAIL_MS) // FRAME_MS
            frames = frames[: len(frames) - max(drop, 0)]
        return b"".join(frames)
