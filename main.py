"""Conductor-Logic-Pro-v1 — entry point."""
import sys

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication

from ui.setup_screen import (
    DisclaimerScreen,
    InputMonitoringScreen,
    PermissionScreen,
    QuestionsDialog,
    has_input_monitoring_permission,
    has_screen_recording_permission,
    is_questions_asked,
    is_setup_complete,
    mark_setup_complete,
)
from ui.chat_window import ChatWindow


class ConductorApp(QApplication):
    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self._chat_window: ChatWindow | None = None
        self._screen = None  # holds the current onboarding screen so it isn't GC'd

    def event(self, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.ApplicationActivate
            and self._chat_window is not None
            and not self._chat_window.isVisible()
        ):
            self._chat_window.open_from_dock()
        return super().event(event)


def _onboarded(app: "ConductorApp") -> None:
    """Route to chat for returning users, otherwise run first-run onboarding."""
    if is_setup_complete():
        _launch_chat(app)
    else:
        _show_disclaimer(app)


def _check_server(url: str) -> None:
    import httpx
    try:
        httpx.get(url, timeout=2)
    except httpx.ConnectError:
        print(f"[conductor] WARNING: server unreachable at {url} — is Docker running? `docker compose -f docker-compose.local.yml up -d` inside server/")
    except Exception:
        pass  # any other error (e.g. 404, 401) means the server is up


def main() -> None:
    from config import SERVER_BASE_URL
    print(f"[conductor] server → {SERVER_BASE_URL}")
    _check_server(SERVER_BASE_URL)
    app = ConductorApp(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.aboutToQuit.connect(lambda: app._chat_window and app._chat_window.prepare_for_quit())

    if not has_screen_recording_permission():
        _show_permission(app)
    elif not has_input_monitoring_permission():
        _show_input_monitoring(app)
    else:
        _onboarded(app)

    sys.exit(app.exec())


def _show_permission(app: ConductorApp) -> None:
    perm = PermissionScreen()
    app._screen = perm
    perm.finished.connect(lambda: _on_permission_done(perm, app))
    perm.show()


def _on_permission_done(perm: PermissionScreen, app: ConductorApp) -> None:
    perm.close()
    if not has_input_monitoring_permission():
        _show_input_monitoring(app)
    else:
        _onboarded(app)


def _show_input_monitoring(app: ConductorApp) -> None:
    screen = InputMonitoringScreen()
    app._screen = screen
    screen.finished.connect(lambda: _on_input_monitoring_done(screen, app))
    screen.show()


def _on_input_monitoring_done(screen: InputMonitoringScreen, app: ConductorApp) -> None:
    screen.close()
    _onboarded(app)


def _show_disclaimer(app: ConductorApp) -> None:
    disclaimer = DisclaimerScreen()
    app._screen = disclaimer
    disclaimer.finished.connect(lambda: _on_disclaimer_done(disclaimer, app))
    disclaimer.show()


def _on_disclaimer_done(disclaimer: DisclaimerScreen, app: ConductorApp) -> None:
    disclaimer.close()
    mark_setup_complete()
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
    window.show()


if __name__ == "__main__":
    main()
