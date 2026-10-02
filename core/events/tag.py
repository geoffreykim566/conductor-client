"""Marks Conductor's own synthetic CGEvents, and checks it may post them at all.

Every event Conductor posts carries SYNTHETIC_EVENT_TAG so the interrupt tap
(core.automation.interrupt_tap) can tell our keystrokes from real user input.
"""
import Quartz


# Marks every CGEvent Conductor itself posts, so core.automation.interrupt_tap's
# CGEventTap can tell "our own synthetic keystroke" from "genuinely real
# input" — without this, a preemptive any-key interrupt would abort a
# walkthrough on its own first synthetic keystroke, every time.
SYNTHETIC_EVENT_TAG = 0x434F4E44  # "COND" in ASCII, arbitrary marker


def tag_synthetic(event) -> None:
    Quartz.CGEventSetIntegerValueField(event, Quartz.kCGEventSourceUserData, SYNTHETIC_EVENT_TAG)


def check_event_permission(prompt: bool = True) -> bool:
    """True if synthetic-event posting is allowed (Accessibility granted)."""
    preflight = getattr(Quartz, "CGPreflightPostEventAccess", None)
    if preflight is None:
        return True  # too old to check — attempt and observe
    if preflight():
        return True
    if prompt:
        Quartz.CGRequestPostEventAccess()
    return False
