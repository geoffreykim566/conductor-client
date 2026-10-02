"""StepAbort: the one failure a step run reports."""


class StepAbort(RuntimeError):
    """A step failed its act→verify contract; the path must stop here."""
