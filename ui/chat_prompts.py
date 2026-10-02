"""Prompts ChatWindow pops over the chat: feedback request and available update (mixin)."""
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from config import FEEDBACK_PROMPT_REMAINING_THRESHOLDS, WEBSITE_URL
from core.net.update_checker import UpdateChecker
from core.state.prefs import is_feedback_never_show
from ui.onboarding.feedback_dialog import FeedbackDialog
from ui.onboarding.update_popup import UpdatePopup


class ChatPromptsMixin:
    """Mixed into ChatWindow; owns _feedback_dialog, _update_popup and _update_checker."""

    # --- feedback prompt ---
    def _maybe_show_feedback_prompt(self, remaining: int) -> None:
        if is_feedback_never_show():
            return
        if remaining in FEEDBACK_PROMPT_REMAINING_THRESHOLDS:
            self._feedback_dialog = FeedbackDialog()
            self._feedback_dialog.closed.connect(self._on_feedback_dialog_closed)
            self._feedback_dialog.show()

    def _on_feedback_dialog_closed(self) -> None:
        self._feedback_dialog = None

    # --- update check ---
    def _start_update_check(self) -> None:
        self._update_checker = UpdateChecker()
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.start()

    def _on_update_available(self, version: str) -> None:
        if self._update_popup is not None and self._update_popup.isVisible():
            return
        self._update_popup = UpdatePopup(version)
        self._update_popup.get_clicked.connect(self._on_update_get)
        self._update_popup.show()

    def _on_update_get(self) -> None:
        QDesktopServices.openUrl(QUrl(WEBSITE_URL))
        if self._update_popup is not None:
            self._update_popup.close()
