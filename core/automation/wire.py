"""Translate the server's wire-schema walkthrough steps into executor step dicts (pure)."""


# Menu parents whose sub-items open a persistent, named settings pane/tab
# (Audio, Recording, MIDI, Metronome, Smart Tempo, Plug-in Manager...) rather
# than firing an instant command/toggle (Low Latency Monitoring Mode, Bypass
# All Control Surfaces) that closes the menu and leaves nothing on screen to
# verify. Derived empirically from every terminal menu step in the KB.
_TABBED_PANE_PARENTS = {"Settings", "Project Settings"}


def _anchor_text(step: dict) -> list[str] | None:
    """OCR text that appearing on screen proves `step` has become reachable —
    used to auto-derive a preceding menu/key step's `expect`. None if `step`'s
    kind has no fixed, derivable anchor (e.g. `choose`, whose value is chosen
    at runtime)."""
    kind = step["kind"]
    if kind == "click_value_of":
        return [step["label"]]
    if kind == "click_text":
        val = step["value"]
        return list(val) if isinstance(val, list) else [val]
    if kind == "menu":
        return [step["path"][0]]
    if kind == "key":
        return None  # shortcuts carry no on-screen text of their own
    return None


def _menu_terminal_expect(path: list[str]) -> list[str] | None:
    """Auto-derived `expect` for a *terminal* menu step (no following step to
    borrow anchor text from). Only Settings/Project Settings sub-tabs are
    reliably still on screen, named after the menu item, after the click —
    plain commands/toggles are not; see `_TABBED_PANE_PARENTS`."""
    if len(path) < 2 or path[-2] not in _TABBED_PANE_PARENTS:
        return None
    return [path[-1].rstrip(".").rstrip("…").strip()]


def wire_to_steps(wire_steps: list[dict]) -> list[dict]:
    """Translate server wire-schema `walkthrough_steps` into the executor's
    native step dicts (see runner.py / README "Step kinds" for the vocabulary).

    Wire keys map straight to `kind`: menu_path->menu, shortcut->key,
    click_text->click_text, click_value_of->click_value_of, choose->choose
    (a dropdown route's value; carries the route as `reopen` for revert),
    ax_open_plugin, ax_set_param. Unrecognized keys are dropped rather than
    guessed at (mirrors the server's own stance on legacy path steps).


    `expect` is not KB-authored data — it's derived here. A `menu`/`key` step
    followed by another step defaults to that next step's own anchor text
    (proof the action landed somewhere useful); a terminal `menu` step falls
    back to its own last-hop name only when that's reliably still visible
    (see `_menu_terminal_expect`). A click_text step followed by a
    click_value_of row gets that row's label (a disclosure header: skipped
    when the row already shows); a wire-sent `expect` on a click_text or menu
    is kept (the server's pane-only trim: the dropped row). A `menu` step also
    gets `skip_if_row`, the label of the route's dropdown row further on (or
    that wire-sent row): it's skipped when that row is already on screen and
    uncovered. Other click_text/click_value_of/choose
    steps never get an auto `expect` — their own pre-click OCR match, or a
    following step's structural check (menu appeared/closed), does that job
    instead.

    The last translated step is marked `final: True` (the state-changing
    step gets the confirm-gate hook) — the furthest a path goes, a `choose`
    when the route picks a dropdown value.
    """
    steps: list[dict] = []
    for wire in wire_steps:
        if "menu_path" in wire:
            st = {"kind": "menu", "path": list(wire["menu_path"])}
            if wire.get("expect"):   # pane-only route: the dropped row it opens onto
                st["expect"] = list(wire["expect"])
                st["skip_if_row"] = list(wire["expect"])
            steps.append(st)
        elif "shortcut" in wire:
            steps.append({"kind": "key", "value": wire["shortcut"]})
        elif "click_value_of" in wire:
            steps.append({"kind": "click_value_of", "label": wire["click_value_of"]})
        elif "click_text" in wire:
            st = {"kind": "click_text", "value": wire["click_text"]}
            if wire.get("expect"):   # pane-only route: the dropped row it reveals
                st["expect"] = list(wire["expect"])
            steps.append(st)
        elif "ax_open_plugin" in wire:
            st = {"kind": "ax_open_plugin", "value": wire["ax_open_plugin"]}
            if wire.get("new"):
                st["new"] = True
            if wire.get("track"):
                st["track"] = wire["track"]
            steps.append(st)
        elif "ax_set_param" in wire:
            steps.append({"kind": "ax_set_param", "value": dict(wire["ax_set_param"])})
        elif "choose" in wire:
            # the row to read back is the dropdown's label (click_value_of);
            # a click_text dropdown has none -- the chosen text itself is checked
            prev = steps[-1] if steps else {}
            steps.append({"kind": "choose", "value": wire["choose"],
                          "row": prev.get("label") if prev.get("kind") == "click_value_of" else None,
                          "reopen": list(wire.get("reopen") or []),
                          # menu title -> the control's shorter display ("On + Align Bars" -> "Bars")
                          "shows": dict(wire.get("shows") or {})})

    for i, step in enumerate(steps):
        nxt = steps[i + 1] if i + 1 < len(steps) else None
        # a click that reveals a settings row (a disclosure header): the row is
        # its expect, so it's skipped when already open. Only this pairing --
        # a dropdown click_text's own label can equal the next step's anchor
        # (flex: "Flex Pitch"), where skipping would be wrong.
        if step["kind"] == "click_text" and nxt is not None and nxt["kind"] == "click_value_of":
            step["expect"] = _anchor_text(nxt)
            continue
        if step["kind"] not in ("menu", "key") or step.get("expect"):   # wire-sent: kept
            continue
        if step["kind"] == "menu":
            # the settings row this route leads to: showing means the pane is open
            row = next((s["label"] for s in steps[i + 1:] if s["kind"] == "click_value_of"), None)
            if row:
                step["skip_if_row"] = [row]
        if nxt is not None:
            expect = _anchor_text(nxt)
        elif step["kind"] == "menu":
            expect = _menu_terminal_expect(step["path"])
        else:
            expect = None
        if expect is not None:
            step["expect"] = expect

    if steps:
        steps[-1]["final"] = True
    return steps
