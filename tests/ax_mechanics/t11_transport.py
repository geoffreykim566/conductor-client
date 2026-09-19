"""T11 — read-only: is transport (play/record) state, tempo, and the CPU meter
AX-readable from the main window?"""
import ApplicationServices as AS
from tests.ax_mechanics._ax_common import *

KEYS = ("play", "record", "stop", "cycle", "metronome", "tempo", "cpu", "load", "transport", "control bar", "lcd", "position")


def main():
    banner("T11 transport / meter readability")
    app = app_element(); mw = main_window(app)
    hits = find_all(mw, lambda e: any(k in ((desc(e) or "") + " " + (title(e) or "")).lower() for k in KEYS), maxd=12)
    for e in hits[:60]:
        print(f"  {role(e)} title={title(e)!r} desc={desc(e)!r} value={repr(value(e))[:40]} actions={ax_action_names(e)}")
    result("transport-ish nodes found", bool(hits), f"{len(hits)} nodes")


if __name__ == "__main__":
    main()
