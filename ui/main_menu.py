"""The ☰ dropdown in the controls row: New Chat, History, Settings, Report Bug."""
from PySide6.QtCore import Signal

from ui.glass_menu import GlassMenu

_ITEMS = (
    ("new_chat", "New Chat"),
    ("history", "History"),
    ("settings", "Settings"),
    ("report_bug", "Report Bug"),
)


class MainMenu(GlassMenu):
    """The shared glass menu with the app's items. Emits `picked(key)`."""

    picked = Signal(str)

    def __init__(self) -> None:
        super().__init__([(label, lambda k=key: self.picked.emit(k), True) for key, label in _ITEMS])
