import json

from config import VERSION
from core.state import identity, prefs, song_history
from core.state.config_store import read_config, write_config
from core.state.conversation import Conversation


def test_read_config_missing_or_corrupt_is_empty(tmp_config):
    assert read_config() == {}
    tmp_config.write_text("{not json")
    assert read_config() == {}


def test_write_then_read_round_trips(tmp_config):
    write_config({"a": 1})
    assert json.loads(tmp_config.read_text()) == {"a": 1}
    assert read_config() == {"a": 1}


def test_identity_token_lifecycle(tmp_config):
    assert identity.get_token() is None
    identity.save_token("abc.sig")
    assert identity.get_token() == "abc.sig"
    identity.clear_token()
    assert identity.get_token() is None


def test_prefs_share_the_file_with_identity(tmp_config):
    identity.save_token("t")
    prefs.set_auto_run(True)
    prefs.mark_setup_complete()
    data = read_config()
    assert data["conductor_token"] == "t"
    assert data["auto_run_actions"] is True
    assert prefs.auto_run() and prefs.is_setup_complete()
    assert not prefs.is_questions_asked()


def test_window_geometry(tmp_config):
    assert prefs.get_saved_window_size() is None
    prefs.save_window_size(400, 600)
    prefs.save_window_pos(0, 25)
    assert prefs.get_saved_window_size() == (400, 600)
    assert prefs.get_saved_window_pos() == (0, 25)
    prefs.clear_window_size()
    prefs.clear_window_pos()
    assert prefs.get_saved_window_size() is None
    assert prefs.get_saved_window_pos() is None


def test_feedback_opt_out_resets_on_new_version(tmp_config):
    write_config({"feedback_never_show": True, "feedback_last_version": "0.0.1"})
    prefs.reset_feedback_for_new_version()
    assert not prefs.is_feedback_never_show()
    assert read_config()["feedback_last_version"] == VERSION
    prefs.mark_feedback_never_show()
    prefs.reset_feedback_for_new_version()
    assert prefs.is_feedback_never_show()


def test_song_history_save_update_and_clear(tmp_history):
    conv = Conversation()
    conv.add_user("hi")
    conv.add_assistant("hello")
    song_history.save_session("s1", conv.messages(), [{"opaque": 1}])
    conv.append_to_last_assistant(" there")
    song_history.save_session("s1", conv.messages(), None)
    sessions = song_history.load_sessions()
    assert len(sessions) == 1
    assert sessions[0]["messages"][1]["text"] == "hello there"
    assert sessions[0]["server_history"] is None
    song_history.clear_all()
    assert song_history.load_sessions() == []


def test_conversation_reload_keeps_ratings():
    conv = Conversation()
    conv.load_messages([{"role": "user", "text": "q"},
                        {"role": "assistant", "text": "a", "event_id": "e1", "rating": -1}])
    assert conv.last_user().text == "q"
    assert conv.last_assistant().rating == -1
    assert conv.last_assistant().event_id == "e1"
