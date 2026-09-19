"""T2 — toggles via AXPress: track Mute + Solo on 'Audio 1' (with screenshot
evidence, since July's Mute pass was AX self-report only) and the Control Bar
Inspector checkbox. Each flips, verifies by RE-FINDING the element, reverts."""
import time
import ApplicationServices as AS
from tests.ax_mechanics._ax_common import *


def fresh_header_control(mw, track, d):
    h = track_header(mw, track)
    return find_child(h, AS.kAXDescriptionAttribute, d) if h is not None else None


def flip(app, mw, name, getter, evidence=None):
    el = getter()
    if el is None:
        result(name, False, "control not found"); return
    before = value(el)
    assert_frontmost(f"before {name}")
    changed = lambda: (value(getter()) != before) or None
    code = ax_press(el)
    got, dt = wait_until(changed, timeout=1.5)
    mech = "AXPress"
    if not got:
        # False success: AXPress returned ok but nothing changed. Fall back to a
        # real click at the element's AX center (found 2026-09-18 on track Mute/Solo).
        click_at(*center(getter())); mech = f"AXPress false-success (code={code}) -> click_at"
        got, dt = wait_until(changed, timeout=1.5)
    now = value(getter())
    shot = screenshot(evidence) if evidence else None
    result(f"{name} on", bool(got), f"{mech}; value {before!r}->{now!r} after {dt:.2f}s evidence={shot}")
    time.sleep(0.8)
    if mech == "AXPress":
        ax_press(getter())
    else:
        click_at(*center(getter()))
    back, dt2 = wait_until(lambda: (value(getter()) == before) or None, timeout=2.5)
    result(f"{name} revert", bool(back), f"value now {value(getter())!r} after {dt2:.2f}s")
    time.sleep(0.4)


def main():
    banner("T2 toggles")
    app = app_element(); bring_logic_front(); mw = main_window(app)
    flip(app, mw, "Audio 1 Mute", lambda: fresh_header_control(mw, "Audio 1", "Mute"), evidence="t2_mute_on")
    flip(app, mw, "Audio 1 Solo", lambda: fresh_header_control(mw, "Audio 1", "Solo"), evidence="t2_solo_on")
    insp = lambda: find_anywhere(mw, desc_="Inspector", role_="AXCheckBox")
    if insp() is None:
        # control bar buttons sometimes carry title instead of desc
        insp = lambda: find_anywhere(mw, title_="Inspector", role_="AXCheckBox")
    flip(app, mw, "Control Bar Inspector", insp, evidence="t2_inspector")


if __name__ == "__main__":
    main()
