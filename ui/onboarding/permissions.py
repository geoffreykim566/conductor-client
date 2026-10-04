"""Preflight checks for the three macOS permissions onboarding gates on, and a reset for uninstall."""
import subprocess

import Quartz

BUNDLE_ID = "com.conductor.logicpro"  # must match bundle_identifier in conductor.spec
_TCC_SERVICES = ("ScreenCapture", "ListenEvent", "Accessibility")


def has_screen_recording_permission() -> bool:
    return bool(Quartz.CGPreflightScreenCaptureAccess())


def has_input_monitoring_permission() -> bool:
    return bool(Quartz.CGPreflightListenEventAccess())


def has_accessibility_permission() -> bool:
    """Same check as `core.events.tag.check_event_permission` (the card's Run gate)."""
    return bool(Quartz.CGPreflightPostEventAccess())


def reset_permissions() -> None:
    """Forget Conductor's Screen Recording, Input Monitoring and Accessibility grants.
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
