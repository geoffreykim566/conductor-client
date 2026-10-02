"""CenteredDialog: the frameless, centered base window every screen in ui/onboarding uses."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget


class CenteredDialog(QWidget):
    """Frameless, translucent, centered-on-screen dialog with no header bar or
    close button -- the setup-screen aesthetic (bold centered title, plain
    subtitle, full-width primary button, ghost secondary buttons) shared by
    every screen in ui/onboarding: onboarding (PermissionScreen,
    InputMonitoringScreen, DisclaimerScreen, QuestionsDialog) and periodic
    prompts (FeedbackDialog, UpdatePopup). Styling comes from the app-wide
    stylesheet (ui/style.py). Distinct from ui/popup.py's Popup,
    which has a header bar + close button for things dismissed casually
    (Settings, its confirm dialogs, History) -- these two aesthetics are
    deliberately not merged, keep new setup/prompt screens on this one rather
    than hand-rolling the same window-flags/translucency/centering
    boilerplate again.

    Subclasses build their own QVBoxLayout(self.body) -- margins/spacing vary
    slightly per screen, so this only owns what's genuinely identical: window
    flags, translucency, fixed size, the "setupRoot" background widget, and
    screen centering.
    """

    def __init__(self, width: int, height: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(width, height)

        self.body = QWidget(self)
        self.body.setObjectName("setupRoot")
        self.body.setGeometry(0, 0, width, height)

        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - width // 2,
            screen.center().y() - height // 2,
        )
