"""For each Compressor circuit type: set it via the Controls-view popup, sweep every numeric
parameter through every raw position, record readouts, restore originals. Ends on Studio VCA.
Aborts (and restores) on the first dead read. Writes one JSON per model.

usage: sweep_models.py <out_dir> <model> [<model> ...]
"""
import json
import sys
import time

import ApplicationServices as AS

sys.path.insert(0, "/Users/geoffreykim/Desktop/conductor/client")
from core import ax  # noqa: E402
from core.automation.logic_focus import activate_logic  # noqa: E402
from core.ax.controls_view import param_rows, set_view  # noqa: E402
from core.ax.menus import dismiss_menus, open_menu_of  # noqa: E402
from core.ax.primitives import ax_get, ax_press, ax_set, children, role, title, value  # noqa: E402

out_dir, models = sys.argv[1], sys.argv[2:]
FINAL_MODEL = "Studio VCA"


class Dead(Exception):
    pass


def norm(s):
    return " ".join(str(s or "").replace(" ", " ").split()).lower()


def setup():
    activate_logic()
    app = ax.app_element()
    win = ax.plugin_window_for(app, "Compressor")
    if win is None:
        sys.exit("no Compressor window")
    ax.raise_window(win)
    if not set_view(app, win, "Controls"):
        sys.exit("couldn't switch to Controls view")
    time.sleep(0.5)
    return app, win


def set_circuit(app, win, model):
    pop = param_rows(win)["Circuit Type"][1]
    if norm(value(pop)) == norm(model):
        return True
    menu = open_menu_of(app, pop)
    items = children(menu) if menu else []
    it = next((i for i in items if norm(title(i)) == norm(model)), None)
    if it is None:
        print(f"  menu items: {[title(i) for i in items]}")
        dismiss_menus(app)
        return False
    ax_press(it)
    time.sleep(0.8)
    return norm(value(param_rows(win)["Circuit Type"][1])) == norm(model)


def readout(ro):
    prev = value(ro)
    for _ in range(20):
        time.sleep(0.03)
        cur = value(ro)
        if cur == prev:
            return cur
        prev = cur
    return prev


def sweep(win, label):
    rows = param_rows(win)
    plan = {}
    for name, (_, ctl, ro) in rows.items():
        if role(ctl) != "AXSlider" or ro is None:
            continue
        lo, hi = ax_get(ctl, AS.kAXMinValueAttribute), ax_get(ctl, AS.kAXMaxValueAttribute)
        if lo is None or hi is None or hi - lo > 2000:
            continue
        plan[name] = (ctl, ro, int(lo), int(hi), value(ctl))
    table = {"label": label, "circuit_type": value(rows["Circuit Type"][1]), "params": {}}
    try:
        for name, (ctl, ro, lo, hi, orig) in plan.items():
            steps = {}
            for raw in range(lo, hi + 1):
                ax_set(ctl, AS.kAXValueAttribute, float(raw))
                for _ in range(30):
                    if value(ctl) == raw:
                        break
                    time.sleep(0.01)
                got = value(ctl)
                if got is None:
                    raise Dead(f"{name} raw {raw}: element went dead")
                steps[str(raw)] = {"raw_read": got, "readout": readout(ro)}
            table["params"][name] = {"min": lo, "max": hi, "original": orig, "steps": steps}
            print(f"  {name}: {hi - lo + 1} steps; {steps[str(lo)]['readout']!r} .. {steps[str(hi)]['readout']!r}", flush=True)
    finally:
        for name, (ctl, _, _, _, orig) in plan.items():
            ax_set(ctl, AS.kAXValueAttribute, float(orig))
        time.sleep(0.3)
        bad = [(n, value(c), o) for n, (c, _, _, _, o) in plan.items() if value(c) != o]
        if bad:
            # Logic sometimes rebuilds its AX tree mid-run; find the window again and retry by name.
            time.sleep(2.0)
            w2 = ax.plugin_window_for(ax.app_element(), "Compressor")
            r2 = param_rows(w2) if w2 is not None else {}
            for n, (_, _, _, _, o) in plan.items():
                if n in r2:
                    ax_set(r2[n][1], AS.kAXValueAttribute, float(o))
            time.sleep(0.3)
            bad = [(n, value(r2[n][1]) if n in r2 else None, o) for n, (_, _, _, _, o) in plan.items()
                   if n not in r2 or value(r2[n][1]) != o]
        print(f"  restored; mismatches: {bad or 'none'}", flush=True)
    return table


app, win = setup()
try:
    for m in models:
        print(f"[{m}]", flush=True)
        if not set_circuit(app, win, m):
            print(f"  couldn't set circuit type {m!r}; skipping", flush=True)
            continue
        t = sweep(win, m)
        path = f"{out_dir}/table_{m.lower().replace(' ', '_')}.json"
        with open(path, "w") as f:
            json.dump(t, f, indent=1)
        print(f"  wrote {path} (circuit_type={t['circuit_type']!r})", flush=True)
except Dead as e:
    print(f"ABORT: {e}", flush=True)
finally:
    time.sleep(1.0)
    win = ax.plugin_window_for(ax.app_element(), "Compressor") or win
    print(f"final circuit {FINAL_MODEL}: {set_circuit(app, win, FINAL_MODEL)}", flush=True)
