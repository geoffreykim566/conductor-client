"""App-wide stylesheet, applied once at the QApplication level so every
top-level window (main chat window, popups, minimized bubble, onboarding
dialogs) shares the same look without each needing its own setStyleSheet call.

Every value here is a ui/theme.py token -- add new tokens there rather than
new literals here."""
from ui.theme import (
    ACCENT,
    ACCENT_FILL,
    ACCENT_FILL_ALPHA,
    ACCENT_HOVER,
    ACCENT_TINT,
    BORDER,
    BORDER_FOCUS,
    BUBBLE_RADIUS,
    BUTTON_RADIUS,
    CHIP_RADIUS,
    DANGER,
    DANGER_BG,
    DANGER_BORDER,
    DIVIDER,
    FIELD_RADIUS,
    FONT_LG,
    FONT_MD,
    FONT_SM,
    FONT_TITLE,
    FONT_XS,
    INPUT_PILL_RADIUS,
    MINIMIZED_RADIUS,
    MONO,
    PANEL,
    PANEL_ALPHA,
    PANEL_BORDER,
    PANEL_BORDER_ALPHA,
    POPUP_ALPHA,
    POPUP_RADIUS,
    ROW_RADIUS,
    SCROLLBAR_WIDTH,
    SEND_RADIUS,
    SURFACE,
    SURFACE_HOVER,
    SURFACE_RAISED,
    TEXT,
    TEXT_BRIGHT,
    TEXT_DIM,
    TEXT_FAINT,
    TEXT_MUTED,
    WHITE,
    rgba,
)

_PANEL_BG = rgba(PANEL, PANEL_ALPHA)
_PANEL_BORDER = f"1px solid {rgba(PANEL_BORDER, PANEL_BORDER_ALPHA)}"
_ACCENT_BG = rgba(ACCENT_FILL, ACCENT_FILL_ALPHA)
_ACCENT_BG_HOVER = rgba(ACCENT_HOVER, ACCENT_FILL_ALPHA)

STYLESHEET = f"""
QWidget#setupRoot, QWidget#guideRoot, QWidget#popupRoot {{
    background-color: {rgba(PANEL, POPUP_ALPHA)};
    border: {_PANEL_BORDER};
    border-radius: {POPUP_RADIUS}px;
}}
QWidget#minimizedRoot {{
    background-color: {_PANEL_BG};
    border: {_PANEL_BORDER};
    border-radius: {MINIMIZED_RADIUS}px;
}}
QWidget#inputPanel {{
    background: transparent;
    border: none;
}}
QWidget#sessionHeader {{
    border-bottom: 1px solid {DIVIDER};
}}
QLabel#title {{
    color: {TEXT_BRIGHT};
    font-family: {MONO};
    font-size: {FONT_TITLE}px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
QLabel#subtitle {{
    color: {TEXT_MUTED};
    font-family: {MONO};
    font-size: {FONT_SM}px;
}}
QLabel#stepLabel {{
    color: {TEXT};
    font-size: {FONT_LG}px;
    padding: 2px 0;
}}
QLabel#sessionTitle {{
    color: {TEXT_MUTED};
    font-family: {MONO};
    font-size: {FONT_XS}px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}}
QLabel#error {{
    color: {DANGER};
    font-family: {MONO};
    font-size: {FONT_SM}px;
}}
QPushButton#headerBtn {{
    background: transparent;
    color: {TEXT_DIM};
    border: none;
    font-size: {FONT_LG}px;
    font-family: {MONO};
    padding: 0;
}}
QPushButton#headerBtn:hover {{
    color: {TEXT};
}}
QFrame#userBubble {{
    background-color: {_ACCENT_BG};
    border-radius: {BUBBLE_RADIUS}px;
}}
QFrame#userBubble QLabel {{
    color: {WHITE};
}}
QFrame#assistantBubble {{
    background-color: {_PANEL_BG};
    border-radius: {BUBBLE_RADIUS}px;
    border: 1px solid {SURFACE_RAISED};
}}
QFrame#assistantBubble QLabel {{
    color: {TEXT};
}}
QTextEdit {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: {ROW_RADIUS}px;
    padding: 6px 10px;
    font-family: {MONO};
    font-size: {FONT_MD}px;
}}
QTextEdit:focus {{
    border: 1px solid {BORDER_FOCUS};
}}
QWidget#inputBubble {{
    background-color: {_PANEL_BG};
    border: {_PANEL_BORDER};
    border-radius: {INPUT_PILL_RADIUS}px;
}}
QTextEdit#bareInput {{
    background: transparent;
    border: none;
    padding: 0;
    font-size: {FONT_SM}px;
}}
QLineEdit {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: {FIELD_RADIUS}px;
    padding: 8px 10px;
    font-family: {MONO};
    font-size: {FONT_MD}px;
}}
QLineEdit:focus {{
    border: 1px solid {BORDER_FOCUS};
}}
QPushButton {{
    background-color: {SURFACE_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: {BUTTON_RADIUS}px;
    font-family: {MONO};
    font-size: {FONT_SM}px;
}}
QPushButton:hover {{
    background-color: {SURFACE_HOVER};
}}
QPushButton:disabled {{
    color: {TEXT_FAINT};
}}
QPushButton#sendBtn {{
    background-color: {_ACCENT_BG};
    color: {WHITE};
    border: none;
    border-radius: {SEND_RADIUS}px;
    font-size: 15px;
}}
QPushButton#sendBtn:hover {{
    background-color: {_ACCENT_BG_HOVER};
}}
QPushButton#sendBtn:disabled {{
    background-color: {SURFACE_RAISED};
    color: {TEXT_FAINT};
}}
QLabel#remainingLabel {{
    background: transparent;
    color: {TEXT_MUTED};
    font-family: {MONO};
    font-size: {FONT_XS}px;
}}
QPushButton#rateBtn {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {CHIP_RADIUS}px;
    font-family: {MONO};
    font-size: {FONT_SM}px;
    padding: 0 6px;
}}
QPushButton#rateBtn:hover {{
    background: {SURFACE};
    border: 1px solid {SURFACE_RAISED};
}}
QPushButton#rateBtn[selected="true"] {{
    background: {SURFACE_RAISED};
    border: 1px solid {ACCENT};
}}
QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: {SCROLLBAR_WIDTH}px;
    /* Bottom margin keeps the track clear of the backdrop panel's rounded
    bottom-right corner (PANEL_RADIUS) so the handle doesn't spill past the
    curve when scrolled all the way down. */
    margin: 0 0 8px 0;
}}
QScrollBar::handle:vertical {{
    background: transparent;
    border-radius: {SCROLLBAR_WIDTH // 2}px;
    min-height: 24px;
}}
QScrollBar[scrolling="true"]::handle:vertical {{
    background: {SURFACE_HOVER};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QPushButton#bubble {{
    background-color: {_PANEL_BG};
    color: {WHITE};
    border: {_PANEL_BORDER};
    border-radius: {MINIMIZED_RADIUS}px;
    font-size: 24px;
}}
QPushButton#bubble:hover {{
    background-color: {rgba(SURFACE_RAISED, PANEL_ALPHA)};
}}
QPushButton#danger {{
    background-color: {DANGER_BG};
    color: {DANGER};
    border: 1px solid {DANGER_BORDER};
    border-radius: {BUTTON_RADIUS}px;
    font-family: {MONO};
    font-size: {FONT_SM}px;
    padding: 6px;
}}
QPushButton#danger:hover {{
    background-color: {DANGER};
    color: {WHITE};
    border-color: {DANGER};
}}
QFrame#sessionRow {{
    background: transparent;
    border-radius: {ROW_RADIUS}px;
}}
QFrame#sessionRow:hover {{
    background: {SURFACE};
}}
QFrame#sessionRowActive {{
    background: {ACCENT_TINT};
    border-radius: {ROW_RADIUS}px;
}}
QLabel#sessionDate {{
    color: {TEXT};
    font-family: {MONO};
    font-size: {FONT_SM}px;
    font-weight: 600;
}}
QLabel#sessionPreview {{
    color: {TEXT_MUTED};
    font-size: {FONT_MD}px;
}}
QLabel#sessionEmpty {{
    color: {TEXT_DIM};
    font-family: {MONO};
    font-size: {FONT_SM}px;
    padding: 32px;
}}
QPushButton#showMeBtn {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: {BUTTON_RADIUS}px;
    color: {ACCENT};
    font-family: {MONO};
    font-size: {FONT_XS}px;
    font-weight: 600;
    padding: 3px 8px;
}}
QPushButton#showMeBtn:hover {{
    border-color: {ACCENT};
    background: {ACCENT_TINT};
}}
QPushButton#showMeBtn:disabled {{
    color: {TEXT_DIM};
    border-color: {SURFACE_RAISED};
}}
QLabel#chatPlaceholder {{
    color: {TEXT_FAINT};
    font-family: {MONO};
    font-size: {FONT_SM}px;
    padding: 32px;
}}
QPushButton#primary {{
    background-color: {_ACCENT_BG};
    color: {WHITE};
    border: none;
    border-radius: {FIELD_RADIUS}px;
    padding: 9px;
    font-family: {MONO};
    font-size: {FONT_MD}px;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background-color: {_ACCENT_BG_HOVER}; }}
QPushButton#primary:disabled {{ background-color: {SURFACE_RAISED}; color: {TEXT_DIM}; }}
QPushButton#secondary {{
    background-color: {SURFACE_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: {FIELD_RADIUS}px;
    padding: 9px;
    font-family: {MONO};
    font-size: {FONT_MD}px;
    font-weight: 600;
}}
QPushButton#secondary:hover {{ background-color: {SURFACE_HOVER}; }}
QPushButton#ghost {{
    background: transparent;
    color: {ACCENT};
    border: none;
    font-family: {MONO};
    font-size: {FONT_SM}px;
    padding: 0;
}}
QPushButton#ghost:hover {{ color: {ACCENT_HOVER}; }}
QCheckBox {{
    color: {TEXT};
    font-family: {MONO};
    font-size: {FONT_MD}px;
    spacing: 8px;
}}
QPushButton#chip {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: {FIELD_RADIUS}px;
    padding: 7px 8px;
    font-family: {MONO};
    font-size: {FONT_SM}px;
}}
QPushButton#chip:hover {{ border: 1px solid {BORDER_FOCUS}; }}
QPushButton#chip[selected="true"] {{
    background-color: {ACCENT};
    border: 1px solid {ACCENT};
    color: {WHITE};
}}
"""
