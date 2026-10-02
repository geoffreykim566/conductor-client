"""Find AX elements under a root: a direct child by attribute, or a depth-limited walk."""
from __future__ import annotations

from core.ax.primitives import ax_get, children, desc, role, title


def find_child(el, attr, target, role_=None):
    for c in children(el):
        if role_ and role(c) != role_:
            continue
        if ax_get(c, attr) == target:
            return c
    return None


def find_anywhere(el, *, desc_=None, title_=None, role_=None, depth=0, maxd=12):
    if el is None:
        return None
    if (desc_ is not None or title_ is not None) and \
            (desc_ is None or desc(el) == desc_) and (title_ is None or title(el) == title_) and \
            (role_ is None or role(el) == role_):
        return el
    if depth >= maxd:
        return None
    for c in children(el):
        r = find_anywhere(c, desc_=desc_, title_=title_, role_=role_, depth=depth + 1, maxd=maxd)
        if r is not None:
            return r
    return None


def find_all(el, pred, depth=0, maxd=12, out=None):
    out = [] if out is None else out
    if el is None:
        return out
    if pred(el):
        out.append(el)
    if depth < maxd:
        for c in children(el):
            find_all(c, pred, depth + 1, maxd, out)
    return out
