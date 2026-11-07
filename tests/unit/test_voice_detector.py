"""PhraseDetector: phrases split at pauses, silence and short noises not sent, idle/cap stops, a silent mic."""
import math
import struct

from core.voice import detector as d

N = d.FRAME_BYTES // 2   # samples per frame


def tone(ms: int, amp: int = 6000) -> bytes:
    n = d.RATE * ms // 1000
    return struct.pack(f"<{n}h", *(int(amp * math.sin(2 * math.pi * 220 * i / d.RATE)) for i in range(n)))


def hiss(ms: int, amp: int = 30) -> bytes:
    n = d.RATE * ms // 1000
    return struct.pack(f"<{n}h", *((amp if i % 2 else -amp) for i in range(n)))


def zeros(ms: int) -> bytes:
    return b"\0\0" * (d.RATE * ms // 1000)


def feed_all(det: d.PhraseDetector, *chunks: bytes) -> tuple[list[bytes], str | None]:
    phrases, stop = [], None
    for c in chunks:
        ev = det.feed(c)
        phrases += ev.phrases
        stop = stop or ev.stop
        if stop:
            break
    return phrases, stop


def test_two_phrases_split_at_a_pause() -> None:
    det = d.PhraseDetector()
    phrases, stop = feed_all(det, hiss(600), tone(1000), hiss(900), tone(800), hiss(900))
    assert len(phrases) == 2, len(phrases)
    assert stop is None
    # speech + preroll + the kept tail, not the whole pause
    assert len(phrases[0]) / 2 / d.RATE < 1.0 + (d.PREROLL_MS + d.TAIL_MS) / 1000 + 0.1


def test_a_short_noise_is_not_sent() -> None:
    det = d.PhraseDetector()
    phrases, _ = feed_all(det, hiss(600), tone(150), hiss(900))
    assert phrases == []


def test_idle_stop_only_after_speech() -> None:
    det = d.PhraseDetector()
    _, stop = feed_all(det, hiss(12_000))
    assert stop is None, "no speech yet: keep waiting"
    phrases, stop = feed_all(det, tone(1000), hiss(int(d.IDLE_STOP_S * 1000) + 500))
    assert len(phrases) == 1 and stop == "idle"


def test_the_cap_stops_and_sends_the_phrase_in_progress() -> None:
    det = d.PhraseDetector(max_seconds=3)
    phrases, stop = feed_all(det, hiss(600), tone(5000))
    assert stop == "cap" and len(phrases) == 1


def test_manual_stop_flushes_the_phrase() -> None:
    det = d.PhraseDetector()
    feed_all(det, hiss(600), tone(1200))
    assert len(det.flush()) == 1


def test_a_mic_sending_only_zeros_is_reported_once() -> None:
    det = d.PhraseDetector()
    flags = [det.feed(zeros(300)).silent_mic for _ in range(10)]
    assert flags.count(True) == 1


def test_zeros_at_start_dont_drag_the_floor_down() -> None:
    """The phone mic sent zeros while starting; the floor must come from the room, not them."""
    det = d.PhraseDetector()
    phrases, _ = feed_all(det, zeros(800), hiss(600), tone(1000), hiss(900), tone(900), hiss(900))
    assert len(phrases) == 2, len(phrases)
