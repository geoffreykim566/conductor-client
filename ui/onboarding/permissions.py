"""The two macOS permissions setup asks for: their checks, names and requests, and a reset for uninstall."""
import platform
import subprocess
from dataclasses import dataclass
from typing import Callable

import Quartz

from core.events.tag import check_event_permission

BUNDLE_ID = "com.conductor.logicpro"  # must match bundle_identifier in conductor.spec
# ListenEvent (Input Monitoring) is no longer asked for, but older installs were granted it.
_TCC_SERVICES = ("ScreenCapture", "ListenEvent", "Accessibility")
_PANE_URL = "x-apple.systempreferences:com.apple.preference.security?"


def has_screen_recording_permission() -> bool:
    return bool(Quartz.CGPreflightScreenCaptureAccess())


def has_accessibility_permission() -> bool:
    """The card's Run gate, without the prompt, so setup and Run always agree."""
    return check_event_permission(prompt=False)


def accessibility_name(mac_version: str | None = None) -> str:
    """What System Settings calls the Accessibility permission: renamed in macOS 27."""
    version = platform.mac_ver()[0] if mac_version is None else mac_version
    try:
        major = int(version.split(".")[0])
    except ValueError:
        return "Accessibility"
    return "Device Control and Data Access" if major >= 27 else "Accessibility"


@dataclass(frozen=True)
class Permission:
    key: str
    title: str
    detail: str
    check: Callable[[], bool]
    request: Callable[[], object]  # shows macOS's popup (once; later calls do nothing)
    pane: str                      # Privacy_* anchor of its System Settings pane
    live: bool                     # check sees a grant without a quit and reopen

    @property
    def settings_url(self) -> str:
        return _PANE_URL + self.pane


def setup_permissions() -> tuple[Permission, ...]:
    """In the order setup asks: Accessibility turns on in place, Screen Recording
    needs macOS's quit and reopen, so it goes last (README "Quirks & why")."""
    return (
        Permission("accessibility", accessibility_name(),
                   "Clicks, types and listens for your stop key in Logic Pro when you run a card.",
                   has_accessibility_permission, check_event_permission,
                   "Privacy_Accessibility", live=True),
        Permission("screen", "Screen Recording",
                   "Reads Logic Pro's windows to find controls.",
                   has_screen_recording_permission, Quartz.CGRequestScreenCaptureAccess,
                   "Privacy_ScreenCapture", live=False),
    )


def all_granted() -> bool:
    return all(p.check() for p in setup_permissions())


def active_index(granted: list[bool]) -> int | None:
    """The row whose button is live: the first not granted, or None when all are."""
    return next((i for i, g in enumerate(granted) if not g), None)


def reset_permissions() -> None:
    """Forget Conductor's permission grants.
    Best-effort: a failed reset must never block uninstall. Always scoped to our bundle id
    (`tccutil reset <service>` alone would reset every app)."""
    for service in _TCC_SERVICES:
        try:
            subprocess.run(
                ["/usr/bin/tccutil", "reset", service, BUNDLE_ID],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass
