"""Source-link chips for an assistant bubble (mixin for MessageWidget)."""
from PySide6.QtWidgets import QLabel, QSizePolicy

from ui.message.styles import system_font
from ui.theme import CHIP_RADIUS, SURFACE_RAISED, TEXT_SECONDARY


class SourcesMixin:
    """Needs `self._role` and `self._bubble_layout` from MessageWidget."""

    def set_sources(self, sources: list) -> None:
        """Add source chips inside the bubble, stacked vertically (research turns only)."""
        url_sources = [s for s in sources if s.get("url")]
        if not url_sources or self._role != "assistant":
            return
        for src in url_sources[:3]:
            title = src.get("title") or src.get("url", "")
            if len(title) > 44:
                title = title[:42] + "…"
            lbl = QLabel(
                f'<a href="{src["url"]}" style="color:{TEXT_SECONDARY};text-decoration:none;">{title}</a>'
            )
            lbl.setOpenExternalLinks(True)
            lbl.setFont(system_font(10))
            lbl.setStyleSheet(
                f"QLabel {{ background-color: {SURFACE_RAISED}; color: {TEXT_SECONDARY};"
                f" border-radius: {CHIP_RADIUS}px; padding: 2px 8px; }}"
            )
            lbl.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
            self._bubble_layout.addWidget(lbl)
