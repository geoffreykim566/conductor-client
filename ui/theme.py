"""Single source of truth for every UI token: colors, type, geometry.

Anything visual that more than one widget/stylesheet rule shares lives here
and nowhere else, so two places can't drift apart (the 2026-09 window/panel
mismatch came from a left inset hand-copied into four files). One-off values
that only one widget uses can stay local to that widget.

Colors are role-named hex strings; use rgba()/qcolor() below when a rule
needs transparency or a QPainter color, so paint code and QSS derive from
the same literal.
"""
from PySide6.QtGui import QColor

# --- Colors: surfaces -------------------------------------------------------
PANEL = "#1c1c1e"            # frosted panels (bubbles backdrop, input pill, popups)
PANEL_ALPHA = 0.82
POPUP_ALPHA = 0.9
PANEL_BORDER = "#2a2a2c"
PANEL_BORDER_ALPHA = 0.6
SURFACE = PANEL              # same grey, opaque (fields, hover rows, cards)
SURFACE_RAISED = "#2c2c2e"   # buttons, chips, assistant-bubble border
SURFACE_HOVER = "#38383a"
BORDER = "#38383a"
BORDER_FOCUS = "#48484a"
DIVIDER = PANEL_BORDER

# --- Colors: text -----------------------------------------------------------
TEXT = "#ebebf5"
TEXT_BRIGHT = "#f2f2f7"
TEXT_SECONDARY = "#8e8e93"
TEXT_MUTED = "#636366"
TEXT_DIM = "#48484a"
TEXT_FAINT = "#3a3a3c"
WHITE = "#ffffff"

# --- Colors: accent / status ------------------------------------------------
ACCENT = "#0a84ff"
ACCENT_HOVER = "#409cff"
ACCENT_FILL = "#086ed4"      # translucent blue fills (user bubble, primary, send)
ACCENT_FILL_ALPHA = 0.78
ACCENT_TINT = "#1c2a3a"      # dark-blue wash behind accent text / active rows
SUCCESS = "#30d158"
SUCCESS_TINT = "#1c3a2a"
DANGER = "#ff453a"
DANGER_BG = "#2a1515"
DANGER_BORDER = "#3a2020"

# --- Typography -------------------------------------------------------------
MONO = '"Menlo", monospace'
FONT_XS = 10
FONT_SM = 11
FONT_MD = 12
FONT_LG = 13
FONT_TITLE = 14

# --- Window -----------------------------------------------------------------
WINDOW_WIDTH = 350
WINDOW_HEIGHT = 500
MIN_WINDOW_WIDTH = 230
MIN_WINDOW_HEIGHT = 380
MAX_WINDOW_WIDTH = 630
MAX_WINDOW_HEIGHT = 1000
WINDOW_MARGIN = 20           # distance from screen edge when anchored
MINIMIZED_SIZE = 60          # collapsed bubble, px square

# --- Shape ------------------------------------------------------------------
PANEL_RADIUS = 18
BUBBLE_RADIUS = 16
POPUP_RADIUS = 14
ROW_RADIUS = 10
FIELD_RADIUS = 8
BUTTON_RADIUS = 6
CHIP_RADIUS = 4
MINIMIZED_RADIUS = MINIMIZED_SIZE // 2

# --- Controls ---------------------------------------------------------------
CONTROL_SIZE = 38            # text field height and send button diameter
INPUT_PILL_PADDING = 4       # inputBubble's inner margin around those controls
INPUT_PILL_RADIUS = CONTROL_SIZE // 2 + INPUT_PILL_PADDING  # fully capsule ends
SEND_RADIUS = CONTROL_SIZE // 2                             # perfect circle
ICON_BTN_SIZE = 20
SCROLLBAR_WIDTH = 4
SCROLLBAR_GUTTER = 6         # keeps the track inboard of the panel's rounded edge


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgba(hex_color: str, alpha: float) -> str:
    r, g, b = _rgb(hex_color)
    return f"rgba({r}, {g}, {b}, {alpha})"


def qcolor(hex_color: str, alpha: float = 1.0) -> QColor:
    c = QColor(hex_color)
    c.setAlphaF(alpha)
    return c
