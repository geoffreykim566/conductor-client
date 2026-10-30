"""Shared fonts and label styles for the message bubble and walkthrough card.

Everything is the app font (SF Pro), step lines included."""
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ui.theme import DANGER, TEXT, TEXT_DIM, TEXT_MUTED, TEXT_SECONDARY

STEP_STYLE = f"QLabel {{ color: {TEXT_MUTED}; padding-left: 2px; }}"
STEP_ACTIVE_STYLE = f"QLabel {{ color: {TEXT}; font-weight: 600; padding-left: 2px; }}"
STEP_FAILED_STYLE = f"QLabel {{ color: {DANGER}; font-weight: 600; padding-left: 2px; }}"
HINT_STYLE = f"QLabel {{ color: {TEXT_DIM}; padding-left: 2px; }}"
STATUS_ERROR_STYLE = f"QLabel {{ color: {DANGER}; padding-left: 2px; margin-top: 4px; }}"
CARD_BUTTON_W = 140
CARD_BUTTON_H = 32
STATUS_INFO_STYLE = f"QLabel {{ color: {TEXT_SECONDARY}; padding-left: 2px; margin-top: 4px; }}"


def system_font(size: int = 13) -> QFont:
    font = QApplication.font()
    font.setPointSize(size)
    return font
