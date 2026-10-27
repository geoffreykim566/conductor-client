"""Move the app's data into config.APP_SUPPORT_DIR at launch, before anything reads it."""
import shutil
from pathlib import Path

from config import APP_SUPPORT_DIR, DATA_DIR_MARKER, LEGACY_APP_SUPPORT_DIR


def prepare_data_dir(target: Path = APP_SUPPORT_DIR, legacy: Path = LEGACY_APP_SUPPORT_DIR) -> None:
    """Conductor-v3 replaces whatever is in `target` (pre-v3 leftovers or nothing);
    without it, pre-v3 leftovers are cleared. `target` is always ours: config only
    picks a dir that's empty or holds our data."""
    if legacy.is_dir():
        if target.exists():
            shutil.rmtree(target)
        legacy.rename(target)
    elif target.is_dir() and not (target / DATA_DIR_MARKER).exists():
        shutil.rmtree(target)   # pre-v3 data: its token and history don't carry over
    target.mkdir(parents=True, exist_ok=True)
    (target / DATA_DIR_MARKER).touch()
