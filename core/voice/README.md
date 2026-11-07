# core/voice

Voice input below the UI: opening the chosen microphone, cutting speech into phrases at pauses,
and handing each phrase on as a WAV. The server call is `core/net/voice.py`; the pill and its
behaviour are `ui/mic_button.py` and `ui/voice_controller.py`.

## Files
- `detector.py` - `PhraseDetector`: 16 kHz mono PCM in, finished phrases, idle/cap stops and a silent-mic flag out. Pure, unit-tested.
- `recorder.py` - `VoiceRecorder`: the microphone permission, `QAudioSource` on the chosen input, the detector; emits WAV phrases.
- `devices.py` - the Mac's inputs, and resolving the saved pick (by id, falling back to the default).

## How it works
Pressing the mic asks macOS for the microphone the first time (`QMicrophonePermission`), then
records the input saved in `prefs.mic_device()` at 16 kHz mono 16-bit. Each ~30 ms frame's level
is compared with a noise floor; speech that ends in a 0.7 s pause becomes a phrase (with 240 ms
before it and 200 ms of the pause), and anything else is never sent. Recording stops after 10 s
without speech (counted from the first speech) or at the cap: 60 s, or the seconds left today if fewer.

## Quirks & why
### Loudness, not a speech model (user call 11-07)
Tested live 11-07 (`voice-log.md`): with the room quiet the phrases split cleanly and nothing
silent was sent; loud music from a speaker counted as speech, so the idle stop didn't fire and
music clips were sent (the transcription model returns nothing for them). Accepted: most people
use headphones or pause the music to talk, and the 1-minute cap and daily limit bound the cost.
Silero VAD is the drop-in if it matters: only `detector.py` changes.

### The noise floor
The floor is the 20th percentile of the last ~3 s, and it can only rise 0.05 dB per frame. With a
plain running average, the phone mic's start-up zeros dragged it to -78 dB in a -60 dB room and a
22 s stretch went as one phrase; with an unlimited percentile, one long sentence lifted the floor to
the voice and split mid-sentence. Digital zeros are skipped (a mic still starting up).

### Silent mics
An input can open with no error and send only zeros (the MacBook mic with the lid closed did, 11-07).
After 1.5 s of nothing but zeros the recorder says so once, and the UI suggests another input.

### Inputs are saved by id
The list reorders and inputs come and go (the iPhone mic, AirPods), so an index pointed at the
wrong mic in testing. `devices.resolve` falls back to the system default when the saved id is gone.

### QtAudio, not QAudio
PySide6 6.11 has both enums; `QAudioSource.error()` returns `QtAudio.Error`, which never equals
`QAudio.Error.NoError`, so the old comparison failed every mic as "couldn't open".
