import json

from config import DATA_DIR_MARKER, is_our_data_dir, resolve_app_support_dir
from core.state.data_dir import prepare_data_dir


def _dirs(tmp_path):
    return tmp_path / "Conductor", tmp_path / "Conductor-v3", tmp_path / "com.conductor.logicpro"


def _write(d, name, data):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(json.dumps(data))


def test_v3_moves_in_and_replaces_pre_v3_data(tmp_path):
    target, legacy, _ = _dirs(tmp_path)
    _write(target, "config.json", {"conductor_token": "old"})
    _write(target, "history.json", {"sessions": ["old"]})
    _write(legacy, "config.json", {"conductor_token": "v3"})
    prepare_data_dir(target, legacy)
    assert not legacy.exists()
    assert json.loads((target / "config.json").read_text()) == {"conductor_token": "v3"}
    assert not (target / "history.json").exists()
    assert (target / DATA_DIR_MARKER).exists()


def test_v3_moves_into_a_new_dir(tmp_path):
    target, legacy, _ = _dirs(tmp_path)
    _write(legacy, "history.json", {"sessions": []})
    prepare_data_dir(target, legacy)
    assert not legacy.exists() and (target / "history.json").exists()


def test_pre_v3_leftovers_alone_are_cleared(tmp_path):
    target, legacy, _ = _dirs(tmp_path)
    _write(target, "config.json", {"conductor_token": "old"})
    prepare_data_dir(target, legacy)
    assert sorted(p.name for p in target.iterdir()) == [DATA_DIR_MARKER]


def test_already_moved_is_left_alone(tmp_path):
    target, legacy, _ = _dirs(tmp_path)
    _write(target, "config.json", {"conductor_token": "t"})
    (target / DATA_DIR_MARKER).touch()
    prepare_data_dir(target, legacy)
    assert json.loads((target / "config.json").read_text()) == {"conductor_token": "t"}


def test_fresh_install_creates_the_dir(tmp_path):
    target, legacy, _ = _dirs(tmp_path)
    prepare_data_dir(target, legacy)
    assert (target / DATA_DIR_MARKER).exists()


def test_another_apps_conductor_dir_is_never_used(tmp_path):
    target, _, fallback = _dirs(tmp_path)
    _write(target, "config.json", {"theme": "dark"})          # not ours
    assert not is_our_data_dir(target)
    assert resolve_app_support_dir(target, fallback) == fallback
    _write(target, "config.json", {"conductor_token": "old"})  # pre-v3, ours
    assert resolve_app_support_dir(target, fallback) == target
    assert resolve_app_support_dir(tmp_path / "missing", fallback) == tmp_path / "missing"
