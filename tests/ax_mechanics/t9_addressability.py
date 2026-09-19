"""T9 — addressability probe (read-only). For a target window, emit a path per
node (role + desc/title + sibling index chain) and check each path re-resolves
3x, and again after the caller closes/reopens the window (run twice).

Usage: python -m tests.ax_mechanics.t9_addressability "<window title substring>"
"""
import sys, time
import ApplicationServices as AS
from tests.ax_mechanics._ax_common import *

INTERESTING = {"AXSlider", "AXCheckBox", "AXPopUpButton", "AXButton", "AXTextField", "AXMenuButton", "AXRadioButton"}


def walk(el, path, out, depth=0, maxd=14):
    kids = children(el)
    for i, c in enumerate(kids):
        seg = (role(c), desc(c) or title(c) or "", i)
        p = path + [seg]
        if role(c) in INTERESTING:
            out.append((p, c))
        if depth < maxd:
            walk(c, p, out, depth + 1, maxd)
    return out


def resolve(root, path, by="name"):
    el = root
    for r, name, idx in path:
        kids = children(el)
        if by == "name" and name:
            cands = [k for k in kids if role(k) == r and (desc(k) or title(k) or "") == name]
            if len(cands) != 1:
                return None, f"name ambiguous/missing ({len(cands)}) at {(r, name)}"
            el = cands[0]
        else:
            if idx >= len(kids) or role(kids[idx]) != r:
                return None, f"index miss at {(r, name, idx)}"
            el = kids[idx]
    return el, "ok"


def fmt(path):
    return "/".join(f"{r}[{n!r}#{i}]" for r, n, i in path)


def main():
    needle = sys.argv[1] if len(sys.argv) > 1 else "Tracks"
    app = app_element()
    win = next((w for w in app_windows(app) if needle in (title(w) or "")), None)
    if win is None:
        print("no window matching", needle, "— open windows:", window_titles(app)); return
    banner(f"T9 addressability: {title(win)!r}")
    t0 = time.time(); nodes = walk(win, [], []); print(f"  {len(nodes)} addressable nodes in {time.time()-t0:.2f}s")
    by_name_ok = by_idx_ok = 0; ambiguous = []
    for p, el in nodes:
        okn = all(resolve(win, p, "name")[0] is not None for _ in range(3))
        oki = all(resolve(win, p, "index")[0] is not None for _ in range(3))
        by_name_ok += okn; by_idx_ok += oki
        if not okn:
            ambiguous.append(fmt(p))
    result("re-resolve by name x3", by_name_ok == len(nodes), f"{by_name_ok}/{len(nodes)} (unnamed/ambiguous need index)")
    result("re-resolve by index x3", by_idx_ok == len(nodes), f"{by_idx_ok}/{len(nodes)}")
    print("  first 25 paths:")
    for p, el in nodes[:25]:
        print("   ", fmt(p), "value=", repr(value(el))[:30])
    if ambiguous:
        print(f"  {len(ambiguous)} name-ambiguous paths, e.g.:")
        for a in ambiguous[:8]:
            print("   ", a)


if __name__ == "__main__":
    main()
