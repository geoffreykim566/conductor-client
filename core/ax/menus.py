"""Open, drill and dismiss Logic's AX menus."""
from __future__ import annotations

import time

from core.ax.app import focused
from core.ax.mouse import click_at
from core.ax.primitives import SETTLE_S, AxError, ax_press, center, children, element_at, parent, role, title, wait_until
from core.events.keyboard import press


def current_menu(app, point=None):
    node = focused(app)
    for _ in range(6):
        if node is None:
            break
        if role(node) == "AXMenu":
            return node
        node = parent(node)
    if point:
        el = element_at(*point)
        p = parent(el) if el is not None else None
        if p is not None and role(p) == "AXMenu":
            return p
    return None


def open_menu_of(app, button):
    """AXPress a menu/popup button and return its open AXMenu (children of the
    button, else via focus, else element-at-position), or None."""
    c = center(button)
    ax_press(button)
    time.sleep(SETTLE_S)
    menu = next((k for k in children(button) if role(k) == "AXMenu"), None) or current_menu(app, c)
    if menu is None and c is not None:
        click_at(*c)
        time.sleep(SETTLE_S)
        menu = next((k for k in children(button) if role(k) == "AXMenu"), None) or current_menu(app, c)
    return menu


def drill(menu, path: list[str], prefer_terminal=("Stereo", "Mono")) -> None:
    """AXPress each hop by title. Handles a terminal item that still opens a
    sub-choice (Mono / Mono->Stereo, Stereo / 5.1)."""
    for i, hop in enumerate(path):
        items = children(menu)
        item = next((it for it in items if (title(it) or "").strip() == hop), None) or \
            next((it for it in items if hop.lower() in (title(it) or "").lower()), None)
        if item is None:
            raise AxError(f"menu item {hop!r} not found; items: {[title(it) for it in items][:20]}")
        ax_press(item)
        time.sleep(SETTLE_S)
        last = i == len(path) - 1
        sub, _ = wait_until(lambda: next((c for c in children(item) if role(c) == "AXMenu" and children(c)), None),
                            timeout=0.8 if last else 1.5)
        if not last:
            if sub is None:
                raise AxError(f"submenu for {hop!r} did not populate")
            menu = sub
        elif sub is not None:
            subs = [c for c in children(sub) if title(c)]
            pick = next((c for c in subs if title(c) in prefer_terminal), subs[0] if subs else None)
            if pick is None:
                raise AxError(f"terminal {hop!r} opened an empty submenu")
            ax_press(pick)
            time.sleep(SETTLE_S)


def dismiss_menus(app) -> None:
    for _ in range(3):
        if current_menu(app) is None:
            return
        press("Escape")
        time.sleep(0.2)
