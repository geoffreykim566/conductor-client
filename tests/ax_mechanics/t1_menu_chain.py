"""T1 — menu-bar chains via AXPress: pre-resolve every element, press back-to-back
with zero reads between, verify a NEW AXWindow appears, close via AXCloseButton."""
import time
import ApplicationServices as AS
from tests.ax_mechanics._ax_common import *

CHAINS = [
    ("Logic Pro", "Settings", "Audio"),
    ("File", "Project Settings", "Smart Tempo"),
]


def resolve(menu_bar, chain):
    el = find_child(menu_bar, AS.kAXTitleAttribute, chain[0])
    if el is None:
        return None
    out = [el]
    for hop in chain[1:]:
        nxt = None
        for cand in find_all(el, lambda e: role(e) == "AXMenuItem" and (title(e) or "").rstrip("…").strip() == hop, maxd=4):
            nxt = cand
            break
        if nxt is None:
            return None
        out.append(nxt)
        el = nxt
    return out


def main():
    banner("T1 menu chains")
    app = app_element()
    bring_logic_front()
    baseline = wait_for_settle(app)
    print("  baseline windows:", baseline)
    menu_bar = ax_get(app, AS.kAXMenuBarAttribute)
    for chain in CHAINS:
        els = resolve(menu_bar, chain)
        if els is None:
            result(" > ".join(chain), False, "could not resolve all menu items via AX")
            continue
        titles = [title(e) for e in els]
        assert_frontmost("before chain")
        t0 = time.time()
        codes = [ax_press(e) for e in els]   # zero delay, zero reads in between
        new, dt = wait_until(lambda: (window_titles(app) - baseline) or None, timeout=4.0)
        assert_frontmost("after chain")
        result(" > ".join(chain), bool(new),
               f"press codes={codes} titles={titles} new windows={new} after {dt:.2f}s")
        if new:
            shot = screenshot("t1_" + chain[-1].lower().replace(" ", "_"), window_title=next(iter(new)))
            print(f"  evidence: {shot}")
            for w in app_windows(app):
                if title(w) in new:
                    closed = close_window(w)
                    gone, dt2 = wait_until(lambda: window_titles(app) == baseline or None, timeout=3.0)
                    result("close " + (title(w) or "?"), bool(gone), f"AXCloseButton found={closed}, back to baseline in {dt2:.2f}s")
        else:
            press("Escape"); time.sleep(0.3)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
