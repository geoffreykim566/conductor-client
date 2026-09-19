"""T3 — AXPopUpButton (track Flex Mode): real click to open, locate the menu via
AXUIElementCopyElementAtPosition + one AXParent hop, AXPress the target item,
verify by re-reading the popup's value; idempotent skip on a second run; revert.
Turns Flex view on first (Tracks toolbar 'Show/Hide Flex') and off after."""
import time
import ApplicationServices as AS
from tests.ax_mechanics._ax_common import *

TRACK = "Audio 1"


def flex_toggle(mw):
    return find_anywhere(mw, desc_="Show/Hide Flex", role_="AXCheckBox")


def flex_popup(mw):
    h = track_header(mw, TRACK)
    return next((c for c in children(h) if role(c) == "AXPopUpButton"), None) if h else None


def set_flex(app, mw, target):
    pop = flex_popup(mw)
    cur = value(pop)
    if cur == target:
        result(f"flex -> {target}", True, f"already {cur!r}: idempotent skip"); return
    c = center(pop); assert_frontmost("before popup click"); click_at(*c); time.sleep(0.6)
    el = element_at(*c)
    menu = ax_get(el, AS.kAXParentAttribute) if el is not None else None
    items = children(menu) if menu is not None and role(menu) == "AXMenu" else []
    if not items:
        # fallback: any layer-101 Logic window with AXMenu at the click point
        print("  menu not found via element-at-position; roles:", role(el), role(menu))
        press("Escape"); result(f"flex -> {target}", False, "no AXMenu located"); return
    item = next((i for i in items if (title(i) or "") == target), None)
    if item is None:
        print("  menu items:", [title(i) for i in items]); press("Escape")
        result(f"flex -> {target}", False, "target item not in menu"); return
    code = ax_press(item)
    got, dt = wait_until(lambda: (value(flex_popup(mw)) == target) or None, timeout=4.0)
    result(f"flex -> {target}", bool(got), f"AXPress code={code}; value {cur!r}->{value(flex_popup(mw))!r} after {dt:.2f}s")


def main():
    banner("T3 flex-mode popup")
    app = app_element(); bring_logic_front(); mw = main_window(app)
    tg = flex_toggle(mw); was = value(tg)
    if not was:
        click_at(*center(tg)); wait_until(lambda: flex_popup(mw), timeout=3.0)
    pop = flex_popup(mw)
    if pop is None:
        result("flex popup visible", False, "no AXPopUpButton in track header"); return
    orig = value(pop); print(f"  original flex mode: {orig!r}")
    set_flex(app, mw, "Flex Pitch")
    time.sleep(0.6)
    set_flex(app, mw, "Flex Pitch")          # idempotent skip
    set_flex(app, mw, "Flex Time - Monophonic")
    screenshot("t3_flex")
    time.sleep(0.6)
    if orig and orig != "Flex Time - Monophonic":
        set_flex(app, mw, orig)
    if not was:
        click_at(*center(flex_toggle(mw))); time.sleep(0.4)
        result("flex view restored", not value(flex_toggle(mw)), f"toggle value {value(flex_toggle(mw))!r}")


if __name__ == "__main__":
    main()
