# core/capture

Pixels from Logic Pro's windows: find them (Quartz window list), capture them, and OCR them
with Apple Vision. The automation layer uses this to find text on screen; the chat worker
uses it to push screenshots as per-turn context.

## Files
- `window_capture.py` - find Logic's on-screen windows, capture one at best resolution, encode context screenshots.
- `ocr_vision.py` - `ocr_words(img)` -> `[{text,left,top,width,height,conf}]` in top-left pixels.

## How it works
`find_all_logic_pro_windows()` matches on window OWNER only (a browser tab titled "Logic Pro"
must not leak in), layers 0/3/8 (plugin windows float at 3 while Logic is active), and raises
`RuntimeError` when none are found. `capture_context_images_b64()` takes the largest windows
first, caps at `config.MAX_CONTEXT_WINDOWS`, downsizes to `MAX_IMAGE_LONG_EDGE` and returns
base64 JPEGs; it never raises. Vision boxes come back normalized with a bottom-left origin and
are flipped to top-left pixels; confidence is per line, applied to each word in it.

`capture_all_plugin_windows`, `capture_window_bestres` and `capture_menubar_strip` have no
callers today (leftovers from the OCR-locate era).

## Quirks & why
### Per-window capture
Each window is captured on its own, never as one union-rect composite: the old composite
(v1's capture) had an unresolved bug where a plugin editor on another display than the main
window ballooned the union rect into a mostly empty canvas and degraded what the model could
read. Per-window keeps each editor at native clarity.

### JPEG screenshots
PNG blew the server's per-image cap: Logic's Compressor in its Studio VCA skin came out ~2.7M
base64 chars as a 1568px PNG, over server-v3's 2M cap, so every turn 422'd while it was open
(2026-09-09, v0.3.0). Vision cost depends on pixel dimensions, not bytes; quality 80 is ~340K
chars with every label legible. Keep `SCREENSHOT_JPEG_QUALITY` >= 70. Anything still over
`MAX_SCREENSHOT_B64_CHARS` is skipped client-side with a log line.

## Adding a capture
Reuse `find_all_logic_pro_windows()` + `capture_one_bestres()`. Context captures must fail
soft (return empty, never raise); automation captures may raise and let the step abort.
