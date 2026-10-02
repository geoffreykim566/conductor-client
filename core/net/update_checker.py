"""Background GitHub Releases version check."""
import json
import urllib.request

from PySide6.QtCore import QThread, Signal

from config import GITHUB_REPO, VERSION

_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _parse_version(tag: str) -> tuple[int, ...]:
    return tuple(int(x) for x in tag.lstrip("v").split("."))


class UpdateChecker(QThread):
    update_available = Signal(str)  # latest version string, e.g. "0.2.4"

    def run(self) -> None:
        try:
            req = urllib.request.Request(_API_URL, headers={"User-Agent": "Conductor"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())
            tag = data.get("tag_name", "")
            if _parse_version(tag) > _parse_version(VERSION):
                self.update_available.emit(tag.lstrip("v"))
        except Exception:
            pass
