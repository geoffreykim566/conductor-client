"""Single source of truth for every UI token: colors, type, geometry.

Anything visual that more than one widget/stylesheet rule shares lives here
and nowhere else, so two places can't drift apart. One-off values
that only one widget uses can stay local to that widget.

Most colors are role-named hex strings; use rgba()/qcolor() below when a rule
needs transparency or a QPainter color, so paint code and QSS derive from
the same literal. The surface fills are ready-made rgba() strings instead
(see "Colors: surfaces").
"""
from PySide6.QtGui import QColor


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


WHITE = "#ffffff"

# --- Colors: surfaces -------------------------------------------------------
# The panels themselves are native glass (ui/glass.py). PANEL is the painted
# stand-in when there's none.
PANEL = "#1c1c1e"
PANEL_ALPHA = 0.82
POPUP_ALPHA = 0.9
PANEL_BORDER = "#2a2a2c"
PANEL_BORDER_ALPHA = 0.6
# Dark wash Qt paints over the glass (ui/glass.py says why not a glass tint).
GLASS_WASH = "#000000"
GLASS_WASH_ALPHA = 0.38
# Everything drawn on a panel is translucent white so the glass shows through
# (an opaque grey reads as a sticker on glass). Already rgba() strings.
SURFACE = rgba(WHITE, 0.06)          # fields, hover rows, assistant bubble
SURFACE_RAISED = rgba(WHITE, 0.10)   # buttons, chips
SURFACE_HOVER = rgba(WHITE, 0.16)
BORDER = rgba(WHITE, 0.10)
BORDER_FOCUS = rgba(WHITE, 0.22)
DIVIDER = rgba(WHITE, 0.08)

# --- Colors: text -----------------------------------------------------------
# A step lighter than Apple's dark label greys: AppKit adds contrast over glass
# with vibrancy, which Qt text doesn't get.
TEXT = "#ebebf5"
TEXT_BRIGHT = "#f2f2f7"
TEXT_SECONDARY = "#a1a1a8"
TEXT_MUTED = "#86868c"
TEXT_DIM = "#727278"
TEXT_FAINT = "#56565b"

# --- Colors: accent / status ------------------------------------------------
ACCENT = "#0a84ff"
ACCENT_HOVER = "#409cff"
ACCENT_FILL = "#086ed4"      # translucent blue fills (user bubble, primary, send)
ACCENT_FILL_ALPHA = 0.78
ACCENT_TINT = rgba(ACCENT, 0.18)   # blue wash behind accent text / active rows
DANGER = "#ff453a"
DANGER_BG = rgba(DANGER, 0.14)
DANGER_BORDER = rgba(DANGER, 0.30)

# --- Typography -------------------------------------------------------------
# UI text is the app font: SF Pro, the macOS system font, which Qt uses by
# default (rules leave font-family out). It can't be bundled and doesn't need
# to be. Menlo stays for technical text: card steps, values, the counter.
MONO = '"Menlo", monospace'
FONT_XS = 11
FONT_SM = 12
FONT_MD = 13
FONT_LG = 13
FONT_TITLE = 15

# --- Window -----------------------------------------------------------------
WINDOW_WIDTH = 350
WINDOW_HEIGHT = 500
MIN_WINDOW_WIDTH = 280       # 270 measured clean but the user still saw a clipped bubble live; slack
MIN_WINDOW_HEIGHT = 380
MAX_WINDOW_WIDTH = 630
MAX_WINDOW_HEIGHT = 1000
WINDOW_MARGIN = 20           # distance from screen edge when anchored
MINIMIZED_SIZE = 60          # collapsed bubble, px square

# --- Shape ------------------------------------------------------------------
PANEL_RADIUS = 22
BUBBLE_RADIUS = 14           # <= half a one-line bubble's height, or Qt squares it
POPUP_RADIUS = 18
ROW_RADIUS = 10
FIELD_RADIUS = 10
BUTTON_RADIUS = 8
CAPSULE_RADIUS = 15          # primary/secondary buttons and chips (>= 30 px tall)
CHIP_RADIUS = 4
MINIMIZED_RADIUS = MINIMIZED_SIZE // 2

# --- Controls ---------------------------------------------------------------
CONTROL_SIZE = 38            # text field height and send button diameter
INPUT_PILL_PADDING = 4       # inputBubble's inner margin around those controls
INPUT_PILL_RADIUS = CONTROL_SIZE // 2 + INPUT_PILL_PADDING  # fully capsule ends
SEND_RADIUS = CONTROL_SIZE // 2                             # perfect circle
ICON_BTN_SIZE = 22
ICON_SIZE = 14               # SF Symbol glyphs in the header buttons
SCROLLBAR_WIDTH = 4
SCROLLBAR_GUTTER = 6         # keeps the track inboard of the panel's rounded edge
