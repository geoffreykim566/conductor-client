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
ACCENT = "#7B2CBF"
ACCENT_HOVER = "#9D4EDD"
ACCENT_FILL = "#7B2CBF"      # translucent purple fills (user bubble, primary, send)
ACCENT_FILL_ALPHA = 0.78
ACCENT_TINT = rgba(ACCENT, 0.18)   # purple wash behind accent text / active rows
BLUE = "#0a84ff"
LINK = BLUE                  # links stay blue (user call)
CHECKBOX = ACCENT            # checkbox squares (ui/checkbox_style.py)
DANGER = "#ff453a"
DANGER_BG = rgba(DANGER, 0.14)
DANGER_BORDER = rgba(DANGER, 0.30)
DANGER_BG_HOVER = rgba(DANGER, 0.26)
DANGER_BORDER_HOVER = rgba(DANGER, 0.50)

# --- Typography -------------------------------------------------------------
# UI text is the app font: SF Pro, the macOS system font, which Qt uses by
# default (rules leave font-family out). It can't be bundled and doesn't need
# to be. Used everywhere, the card's step lines included.
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
MENU_RADIUS = 9              # the ☰ and right-click menus (smaller, like macOS's)
ROW_RADIUS = 10
FIELD_RADIUS = 10
BUTTON_RADIUS = 8
CAPSULE_RADIUS = 15          # primary/secondary buttons and chips (>= 30 px tall)
CHIP_RADIUS = 4
MINIMIZED_RADIUS = MINIMIZED_SIZE // 2

# --- Controls ---------------------------------------------------------------
CONTROL_SIZE = 38            # one-line text field height
OPTIONS_INSET = 8            # the Explain row's inset from the box's inner edge, left and right
SEND_SIZE = CONTROL_SIZE - OPTIONS_INSET   # send button size: its right edge lines up with the mic pill's
MIC_PILL_HEIGHT = 20         # the mic pill on the Explain row, as tall as the Explain toggle
INPUT_PILL_PADDING = 4       # inputBubble's inner margin around those controls
INPUT_PILL_RADIUS = CONTROL_SIZE // 2 + INPUT_PILL_PADDING  # fully capsule ends
# A rounded square whose corner runs parallel to the box's: the box's radius minus the gap
# between them on the right (padding + the Explain row's inset). Same as the Explain toggle's.
SEND_RADIUS = INPUT_PILL_RADIUS - INPUT_PILL_PADDING - OPTIONS_INSET
ICON_BTN_SIZE = 22
ICON_SIZE = 14               # SF Symbol glyphs in the header buttons
WINDOW_ICON_SIZE = 12        # the chat header's minimize and close glyphs
MENU_ICON_WIDTH = 12         # the chat header's ☰ lines
MENU_ICON_SIZE = 9.5         # SF Symbols on the ☰ menu's rows, drawn at this size (not stretched)
MENU_CHECK_SIZE = 8.5        # a picked row's checkmark: smaller and bolder, like macOS's menus
SCROLLBAR_WIDTH = 4
SCROLLBAR_GUTTER = 6         # keeps the track inboard of the panel's rounded edge
