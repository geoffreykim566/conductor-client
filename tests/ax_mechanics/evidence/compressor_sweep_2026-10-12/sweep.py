"""Read-only: every attribute (and parameterized-attribute names) of every element in Logic's
Compressor window; report any value containing the target strings."""
import sys, re
import ApplicationServices as AS
from AppKit import NSWorkspace
sys.path.insert(0, "/Users/geoffreykim/Desktop/conductor/client")
from config import LOGIC_PRO_APP_NAMES

SKIP = {"AXParent", "AXWindow", "AXTopLevelUIElement", "AXChildren", "AXChildrenInNavigationOrder",
        "AXVisibleChildren", "AXContents", "AXFocusedUIElement"}
PAT = re.compile(r"19[.,]5|8[.,]7|\bms\b|51[.,]0|:1\b|\bdB\b", re.I)

def get(el, a):
    err, v = AS.AXUIElementCopyAttributeValue(el, a, None)
    return v if err == 0 else None

def names(el):
    err, n = AS.AXUIElementCopyAttributeNames(el, None)
    return list(n) if err == 0 and n else []

def pnames(el):
    err, n = AS.AXUIElementCopyParameterizedAttributeNames(el, None)
    return list(n) if err == 0 and n else []

pid = next(a.processIdentifier() for a in NSWorkspace.sharedWorkspace().runningApplications()
           if str(a.localizedName()) in LOGIC_PRO_APP_NAMES)
app = AS.AXUIElementCreateApplication(pid)
win = None
for w in get(app, "AXWindows") or []:
    stack = [w]; found = False
    while stack and not found:
        e = stack.pop()
        if "Attack knob" in str(get(e, "AXHelp") or ""): found = True
        stack += list(get(e, "AXChildren") or [])
    if found: win = w; break
if win is None:
    sys.exit("no Compressor editor window found")

n_el = 0; all_attrs = set(); pattrs = set(); hits = []; roles = {}
stack = [(win, 0)]
while stack:
    e, d = stack.pop()
    n_el += 1
    r = str(get(e, "AXRole")); roles[r] = roles.get(r, 0) + 1
    for a in names(e):
        all_attrs.add(a)
        if a in SKIP: continue
        v = get(e, a)
        if v is None: continue
        s = str(v)
        if PAT.search(s) and a not in ("AXHelp",):
            hits.append(f"{r} {a}={s[:120]!r} help={str(get(e,'AXHelp'))[:40]!r}")
    pattrs.update(pnames(e))
    for c in get(e, "AXChildren") or []:
        stack.append((c, d + 1))

print(f"elements={n_el} roles={roles}")
print(f"attribute names seen: {sorted(all_attrs)}")
print(f"parameterized attrs: {sorted(pattrs)}")
print(f"hits ({len(hits)}):"); print("\n".join(hits) or "  none")
