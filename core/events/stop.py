"""Cooperative mid-step stop: posting loops call check_stop() between events."""


class Stopped(Exception):
    """Internal unwind signal for a mid-step stop_event; caught inside
    run_steps() and never propagated as a StepAbort/failure."""


def check_stop(stop_event) -> None:
    if stop_event is not None and stop_event.is_set():
        raise Stopped()
