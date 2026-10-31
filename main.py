"""Conductor client — entry point."""
import sys

from PySide6.QtCore import QEvent
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenuBar

from core.state import run_log
from core.state.data_dir import prepare_data_dir
from core.state.prefs import is_disclaimer_current, is_questions_asked, is_setup_complete, mark_disclaimer_accepted
from ui.chat_window import ChatWindow
from ui.onboarding.disclaimer_screen import DisclaimerScreen
from ui.onboarding.permissions import all_granted
from ui.onboarding.permissions_screen import PermissionsScreen
from ui.onboarding.questions_dialog import QuestionsDialog
from ui.style import STYLESHEET


class ConductorApp(QApplication):
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self._chat_window: ChatWindow | None = None
        self._screen = None  # holds the current onboarding screen so it isn't GC'd
        self._menu_bar: QMenuBar | None = None  # holds the app menu so it isn't GC'd

    def event(self, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.ApplicationActivate
            and self._chat_window is not None
            and not self._chat_window.isVisible()
        ):
            self._chat_window.open_from_dock()
        return super().event(event)


def _onboarded(app: "ConductorApp") -> None:
    """Route to chat for returning users, otherwise run first-run onboarding.
    A returning user who accepted an older disclaimer sees the new one first."""
    if is_setup_complete() and is_disclaimer_current():
        _launch_chat(app)
    else:
        _show_disclaimer(app)


def _check_server(url: str) -> None:
    import httpx
    try:
        httpx.get(url, timeout=2)
    except httpx.ConnectError:
        print(f"[conductor] WARNING: server unreachable at {url} — is Docker running? `docker compose up -d --build` inside server/")
    except Exception:
        pass  # any other error (e.g. 404, 401) means the server is up


def main() -> None:
    prepare_data_dir()  # first: everything below may read config.json
    run_log.install()   # before the first print, so a bug report carries the whole run
    from config import SERVER_BASE_URL
    print(f"[conductor] server → {SERVER_BASE_URL}")
    _check_server(SERVER_BASE_URL)
    app = ConductorApp(sys.argv)
    app.setStyleSheet(STYLESHEET)
    app.setQuitOnLastWindowClosed(False)
    app.aboutToQuit.connect(lambda: app._chat_window and app._chat_window.prepare_for_quit())

    if not all_granted():
        _show_permissions(app)
    else:
        _onboarded(app)

    sys.exit(app.exec())


def _show_permissions(app: ConductorApp) -> None:
    screen = PermissionsScreen()
    app._screen = screen
    screen.finished.connect(lambda: _on_permissions_done(screen, app))
    screen.show()


def _on_permissions_done(screen: PermissionsScreen, app: ConductorApp) -> None:
    screen.close()
    _onboarded(app)


def _show_disclaimer(app: ConductorApp) -> None:
    disclaimer = DisclaimerScreen()
    app._screen = disclaimer
    disclaimer.finished.connect(lambda: _on_disclaimer_done(disclaimer, app))
    disclaimer.show()


def _on_disclaimer_done(disclaimer: DisclaimerScreen, app: ConductorApp) -> None:
    disclaimer.close()
    mark_disclaimer_accepted()
    _show_questions(app)


def _show_questions(app: ConductorApp) -> None:
    if is_questions_asked():
        _launch_chat(app)
        return
    dialog = QuestionsDialog()
    app._screen = dialog
    dialog.closed.connect(lambda: _launch_chat(app))
    dialog.show()


def _launch_chat(app: ConductorApp) -> None:
    window = ChatWindow()
    app._chat_window = window
    _install_menu_bar(app, window)
    window.show()


def _install_menu_bar(app: ConductorApp, window: ChatWindow) -> None:
    """A QMenuBar with no parent window still merges into the native macOS
    menu bar. Settings is given the standard Preferences role so macOS places
    it under the app's own menu (top-left) with the usual Cmd+, shortcut."""
    menu_bar = QMenuBar()
    app._menu_bar = menu_bar
    menu = menu_bar.addMenu("Conductor")
    settings_action = QAction("Settings…", menu_bar)
    settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
    settings_action.triggered.connect(window.open_settings)
    menu.addAction(settings_action)


if __name__ == "__main__":
    main()
