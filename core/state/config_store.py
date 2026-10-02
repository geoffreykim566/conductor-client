"""Read and write the app's single config.json (identity token, prefs, flags)."""
import json

from config import APP_SUPPORT_DIR

CONFIG_PATH = APP_SUPPORT_DIR / "config.json"


def read_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_config(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2))
