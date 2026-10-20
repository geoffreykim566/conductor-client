"""Sweep every numeric Compressor parameter through every raw position in Controls view and
record the readout. Writes the plugin; restores each parameter's original raw at the end.

usage: sweep_table.py <label> <out.json>
"""
import json
import sys
import time

import ApplicationServices as AS

sys.path.insert(0, "/Users/geoffreykim/Desktop/conductor/client")
from core import ax  # noqa: E402
from core.ax.controls_view import param_rows, set_view  # noqa: E402
from core.ax.primitives import ax_get, ax_set, role, value  # noqa: E402

label, out_path = sys.argv[1], sys.argv[2]
app = ax.app_element()
win = ax.plugin_window_for(app, "Compressor")
if win is None:
    sys.exit("no Compressor window open")
if not set_view(app, win, "Controls"):
    sys.exit("couldn't switch to Controls view")
time.sleep(0.5)


def readout(ro):
    """Read twice 30 ms apart until stable (the readout can lag the write)."""
    prev = value(ro)
    for _ in range(20):
        time.sleep(0.03)
        cur = value(ro)
        if cur == prev:
            return cur
        prev = cur
    return prev


rows = param_rows(win)
plan = {}
for name, (cell, ctl, ro) in rows.items():
    if role(ctl) != "AXSlider" or ro is None:
        print(f"skip {name!r}: {role(ctl)}")
        continue
    lo, hi = ax_get(ctl, AS.kAXMinValueAttribute), ax_get(ctl, AS.kAXMaxValueAttribute)
    if lo is None or hi is None or hi - lo > 2000:
        print(f"skip {name!r}: range {lo}..{hi}")
        continue
    plan[name] = (ctl, ro, int(lo), int(hi), value(ctl))
print(f"[{label}] sweeping {len(plan)} params: " + ", ".join(f"{k} {v[2]}..{v[3]} (now {v[4]})" for k, v in plan.items()), flush=True)

ct = value(rows["Circuit Type"][1]) if "Circuit Type" in rows else None
print(f"[{label}] Circuit Type = {ct!r}", flush=True)
table = {"label": label, "circuit_type": ct, "params": {}}
try:
    for name, (ctl, ro, lo, hi, orig) in plan.items():
        t0 = time.time()
        steps = {}
        for raw in range(lo, hi + 1):
            ax_set(ctl, AS.kAXValueAttribute, float(raw))
            for _ in range(30):
                if value(ctl) == raw:
                    break
                time.sleep(0.01)
            got = value(ctl)
            steps[str(raw)] = {"raw_read": got, "readout": readout(ro)}
        table["params"][name] = {"min": lo, "max": hi, "original": orig, "steps": steps}
        mism = sum(1 for k, s in steps.items() if s["raw_read"] != int(k))
        print(f"  {name}: {hi - lo + 1} steps in {time.time() - t0:.1f}s, raw mismatches={mism}; "
              f"{steps[str(lo)]['readout']!r} .. {steps[str(hi)]['readout']!r}", flush=True)
finally:
    for name, (ctl, ro, lo, hi, orig) in plan.items():
        ax_set(ctl, AS.kAXValueAttribute, float(orig))
    time.sleep(0.3)
    bad = [(n, value(c), o) for n, (c, _, _, _, o) in plan.items() if value(c) != o]
    print(f"[{label}] restored; mismatches: {bad or 'none'}", flush=True)
    with open(out_path, "w") as f:
        json.dump(table, f, indent=1)
    print(f"wrote {out_path}", flush=True)
