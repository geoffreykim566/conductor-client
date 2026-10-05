"""Marks Conductor's own synthetic CGEvents, and checks it may post them at all.

Every event Conductor posts carries SYNTHETIC_EVENT_TAG so the interrupt tap
(core.automation.interrupt_tap) can tell our keystrokes from real user input.
"""
import ApplicationServices as AS
import Quartz


# Marks every CGEvent Conductor itself posts, so core.automation.interrupt_tap's
# CGEventTap can tell "our own synthetic keystroke" from "genuinely real
# input" — without this, a preemptive any-key interrupt would abort a
# walkthrough on its own first synthetic keystroke, every time.
SYNTHETIC_EVENT_TAG = 0x434F4E44  # "COND" in ASCII, arbitrary marker


def tag_synthetic(event) -> None:
    Quartz.CGEventSetIntegerValueField(event, Quartz.kCGEventSourceUserData, SYNTHETIC_EVENT_TAG)


def check_event_permission(prompt: bool = True) -> bool:
    """True if synthetic-event posting is allowed (Accessibility granted).

    Uses AXIsProcessTrusted, which reads the live state: CGPreflightPostEventAccess kept
    returning False in the running process after the user toggled Accessibility on (seen
    live 2026-10-04), and CGRequestPostEventAccess showed no prompt. With `prompt`, macOS
    shows its "control this computer" dialog with a button to open the settings."""
    if AS.AXIsProcessTrusted():
        return True
    if prompt:
        AS.AXIsProcessTrustedWithOptions({AS.kAXTrustedCheckOptionPrompt: True})
    return False
