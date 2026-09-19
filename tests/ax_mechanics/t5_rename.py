"""T5 — track rename via double-click -> focused AXTextField -> set -> Return."""
import time
import ApplicationServices as AS
from tests.ax_mechanics._ax_common import *


def main():
    banner("T5 track rename")
    app = app_element(); bring_logic_front(); mw = main_window(app)
    h = track_header(mw, "Audio 1")
    name_el = find_child(h, AS.kAXDescriptionAttribute, "Audio 1", "AXTextField")
    ok, how = set_via_text_field(app, name_el, "AX Test Track")
    renamed, dt = wait_until(lambda: track_header(mw, "AX Test Track"), timeout=3.0)
    result("rename Audio 1 -> AX Test Track", bool(renamed), f"{how}; header found after {dt:.2f}s")
    screenshot("t5_renamed")
    time.sleep(0.8)
    if renamed:
        name_el = find_child(renamed, AS.kAXDescriptionAttribute, "AX Test Track", "AXTextField")
        ok2, how2 = set_via_text_field(app, name_el, "Audio 1")
        back, dt2 = wait_until(lambda: track_header(mw, "Audio 1"), timeout=3.0)
        result("revert", bool(back), f"{how2}; after {dt2:.2f}s")


if __name__ == "__main__":
    main()
