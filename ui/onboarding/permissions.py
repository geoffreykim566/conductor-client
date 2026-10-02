"""Preflight checks for the two macOS permissions onboarding gates on."""
import Quartz


def has_screen_recording_permission() -> bool:
    return bool(Quartz.CGPreflightScreenCaptureAccess())


def has_input_monitoring_permission() -> bool:
    return bool(Quartz.CGPreflightListenEventAccess())
