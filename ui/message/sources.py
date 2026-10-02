"""Confidence-tier badge and source-link chips for an assistant bubble (mixin for MessageWidget)."""
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy

from ui.message.chip import Chip
from ui.message.styles import system_font
from ui.theme import (
    ACCENT,
    ACCENT_TINT,
    CHIP_RADIUS,
    FONT_XS,
    MONO,
    SUCCESS,
    SUCCESS_TINT,
    SURFACE_RAISED,
    TEXT_SECONDARY,
)


class SourcesMixin:
    """Needs `self._role`, `self._outer` and `self._bubble_layout` from MessageWidget."""

    # tier -> (label, background, foreground, hover explanation). Bands are
    # computed server-side (pipeline.py's _confidence_tier).
    _TIER_CHIP = {
        "strong": (
            "Confidence: Strong", ACCENT_TINT, ACCENT,
            "Confirmed against Conductor's verified Logic Pro knowledge base.",
        ),
        "moderate": (
            "Confidence: Moderate", SUCCESS_TINT, SUCCESS,
            "Confirmed against Conductor's verified Logic Pro knowledge base, "
            "but not as confidently as a strong match -- usually this means "
            "the model included its own knowledge alongside it that we "
            "couldn't completely verify.",
        ),
        "research": (
            "Research Verified", ACCENT_TINT, ACCENT,
            "Backed by a live web search for up-to-date information.",
        ),
        "generic": (
            "General Answer", SURFACE_RAISED, TEXT_SECONDARY,
            "The knowledge base didn't have anything for this -- treat this "
            "as general guidance from the model's own knowledge, not a "
            "confirmed answer.",
        ),
    }

    def set_source_tier(self, tier: str) -> None:
        """Add a small confidence badge below the bubble (hover for what it means)."""
        # Badges are disabled; the code below is kept for when they return
        # (see README "Confidence badges disabled").
        return

        if tier not in self._TIER_CHIP or self._role != "assistant" or getattr(self, "_tier_row", None) is not None:
            return
        label_text, bg, fg, tooltip = self._TIER_CHIP[tier]
        chip = Chip(label_text, tooltip)
        chip.setStyleSheet(
            f"QLabel {{ background-color: {bg}; color: {fg}; border-radius: {CHIP_RADIUS}px;"
            f" font-family: {MONO}; font-size: {FONT_XS}px; font-weight: 600;"
            f" padding: 1px 6px; }}"
        )
        chip.setFixedHeight(18)
        chip.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

        row = QHBoxLayout()
        row.setContentsMargins(6, 0, 0, 0)  # indent under the bubble's left edge
        row.addWidget(chip)
        row.addStretch()
        self._outer.addLayout(row)
        self._tier_row = row

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
