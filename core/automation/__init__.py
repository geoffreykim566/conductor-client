"""Walkthrough executor: drive Logic Pro through a translated step list, verify, revert.

Public API (what ui/ and tests use); see README.md for the module map.
"""
from core.automation.errors import StepAbort
from core.automation.executor_thread import ExecutorThread, RevertThread
from core.automation.interrupt_tap import WalkthroughInterruptTap
from core.automation.logic_focus import activate_logic, frontmost_owner, wait_logic_on_screen
from core.automation.revert import revert
from core.automation.runner import run_steps
from core.automation.timing import MENU_SETTLE_S
from core.automation.wire import wire_to_steps
from core.events.tag import check_event_permission

__all__ = [
    "activate_logic",
    "check_event_permission",
    "ExecutorThread",
    "frontmost_owner",
    "MENU_SETTLE_S",
    "revert",
    "RevertThread",
    "run_steps",
    "StepAbort",
    "wait_logic_on_screen",
    "WalkthroughInterruptTap",
    "wire_to_steps",
]
