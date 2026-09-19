"""User preferences, stored next to the identity token in config.json."""
from core.identity import _read_config, _write_config

AUTO_RUN_KEY = "auto_run_actions"


def auto_run() -> bool:
    """True = execute agentic actions without the Run confirm (destructive
    actions still confirm regardless)."""
    return bool(_read_config().get(AUTO_RUN_KEY, False))


def set_auto_run(enabled: bool) -> None:
    data = _read_config()
    data[AUTO_RUN_KEY] = bool(enabled)
    _write_config(data)
