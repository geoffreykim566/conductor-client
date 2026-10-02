"""User preferences and one-shot app flags kept in config.json."""
from config import VERSION
from core.state.config_store import read_config, write_config


AUTO_RUN_KEY = "auto_run_actions"


def auto_run() -> bool:
    """True = execute agentic actions without the Run confirm (destructive
    actions still confirm regardless)."""
    return bool(read_config().get(AUTO_RUN_KEY, False))


def set_auto_run(enabled: bool) -> None:
    data = read_config()
    data[AUTO_RUN_KEY] = bool(enabled)
    write_config(data)


def get_saved_window_size() -> tuple[int, int] | None:
    data = read_config()
    w, h = data.get("window_width"), data.get("window_height")
    if w and h:
        return (int(w), int(h))
    return None


def save_window_size(w: int, h: int) -> None:
    data = read_config()
    data["window_width"] = w
    data["window_height"] = h
    write_config(data)


def clear_window_size() -> None:
    data = read_config()
    data.pop("window_width", None)
    data.pop("window_height", None)
    write_config(data)


def get_saved_window_pos() -> tuple[int, int] | None:
    data = read_config()
    x, y = data.get("window_x"), data.get("window_y")
    if x is not None and y is not None:
        return (int(x), int(y))
    return None


def save_window_pos(x: int, y: int) -> None:
    data = read_config()
    data["window_x"] = x
    data["window_y"] = y
    write_config(data)


def clear_window_pos() -> None:
    data = read_config()
    data.pop("window_x", None)
    data.pop("window_y", None)
    write_config(data)


def is_setup_complete() -> bool:
    """True once a free-tier user has finished onboarding (no key required)."""
    return bool(read_config().get("setup_complete"))


def mark_setup_complete() -> None:
    data = read_config()
    data["setup_complete"] = True
    write_config(data)


def is_questions_asked() -> bool:
    """True once the post-first-message onboarding questions have been shown."""
    return bool(read_config().get("questions_asked"))


def mark_questions_asked() -> None:
    data = read_config()
    data["questions_asked"] = True
    write_config(data)


def is_feedback_never_show() -> bool:
    return bool(read_config().get("feedback_never_show"))


def mark_feedback_never_show() -> None:
    data = read_config()
    data["feedback_never_show"] = True
    write_config(data)


def reset_feedback_for_new_version() -> None:
    """Treat each app update as a fresh request for feedback."""
    data = read_config()
    if data.get("feedback_last_version") != VERSION:
        data.pop("feedback_never_show", None)
        data["feedback_last_version"] = VERSION
        write_config(data)
