"""T4 — exact slider values via double-click -> focused AXTextField -> set -> Return,
on 'Audio 1' Volume and Pan. Records raw<->text scale mapping and read-back lag."""
import time
import ApplicationServices as AS
from tests.ax_mechanics._ax_common import *


def get_sliders(mw):
    h = track_header(mw, "Audio 1")
    vol = find_child(h, AS.kAXDescriptionAttribute, "Volume", "AXSlider")
    pan = next((c for c in children(h) if role(c) == "AXSlider" and c is not vol), None)
    return vol, pan


def peek_text(app, el):
    """Double-click, read the focused text field's current text, then Escape."""
    c = center(el); double_click_at(*c); time.sleep(0.35)
    f = focused(app)
    txt = value(f) if f is not None and role(f) == "AXTextField" else None
    press("Escape"); time.sleep(0.3)
    return txt


def exact(app, mw, which, target_text, expect_change=True):
    vol, pan = get_sliders(mw)
    el = vol if which == "Volume" else pan
    raw0 = value(el)
    txt0 = peek_text(app, el)
    print(f"  {which}: raw={raw0!r} text={txt0!r}")
    ok, how = set_via_text_field(app, el, target_text)
    vol, pan = get_sliders(mw); el = vol if which == "Volume" else pan
    changed, dt = wait_until(lambda: (value(el) != raw0) or None, timeout=3.0)
    raw1 = value(el)
    txt1 = peek_text(app, el)
    result(f"{which} -> {target_text!r}", ok and (raw1 != raw0) == expect_change,
           f"{how}; raw {raw0!r}->{raw1!r} ({dt:.2f}s); text now {txt1!r}")
    return raw0, txt0, raw1


def main():
    banner("T4 slider exact value")
    app = app_element(); bring_logic_front(); mw = main_window(app)
    r0, t0, r1 = exact(app, mw, "Volume", "-6.0")
    if t0 is not None:
        exact(app, mw, "Volume", t0.replace(" dB", "").strip())   # restore original
    p0, pt0, p1 = exact(app, mw, "Pan", "20")
    exact(app, mw, "Pan", "0")
    print(f"  scale notes: volume raw {r0}->{r1} for text {t0!r}->'-6.0'; pan raw {p0}->{p1} for text {pt0!r}->'20'")
    screenshot("t4_after")


if __name__ == "__main__":
    main()
