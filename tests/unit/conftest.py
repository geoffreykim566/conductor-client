"""Shared fixtures: point every config.json / history.json reader at a temp dir."""
import pytest

from core.state import config_store, song_history


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config_store, "CONFIG_PATH", path)
    return path


@pytest.fixture
def tmp_history(tmp_path, monkeypatch):
    path = tmp_path / "history.json"
    monkeypatch.setattr(song_history, "HISTORY_FILE", path)
    return path
