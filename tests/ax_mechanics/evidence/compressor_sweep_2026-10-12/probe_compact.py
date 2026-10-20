"""Read-only: one line per AXSlider (desc, raw, min/max, ValueDescription) in every Logic window."""
import sys
import ApplicationServices as AS
from AppKit import NSWorkspace
sys.path.insert(0, "/Users/geoffreykim/Desktop/conductor/client")
from config import LOGIC_PRO_APP_NAMES

def get(el, a):
    err, v = AS.AXUIElementCopyAttributeValue(el, a, None)
    return v if err == 0 else None

def walk(el, d, out):
    if d > 25: return
    r = get(el, "AXRole")
    if r == "AXSlider": out.append(el)
    for c in list(get(el, "AXChildren") or [])[:300]:
        walk(c, d + 1, out)

pid = next(a.processIdentifier() for a in NSWorkspace.sharedWorkspace().runningApplications()
           if str(a.localizedName()) in LOGIC_PRO_APP_NAMES)
app = AS.AXUIElementCreateApplication(pid)
for w in get(app, "AXWindows") or []:
    out = []; walk(w, 0, out)
    print(f"\n### {get(w,'AXTitle')!r}: {len(out)} sliders")
    if len(out) > 80: print("  (main window, skipped)"); continue
    for s in out:
        print(f"  {str(get(s,'AXDescription')):28} raw={get(s,'AXValue')!s:8} [{get(s,'AXMinValue')}..{get(s,'AXMaxValue')}] shown={get(s,'AXValueDescription')!r}")
