"""StreamWorker: a failed turn reaches the user as one of chat_stream.ERROR_TEXT, never raw."""
from core.net import llm_client
from core.net.chat_stream import ERROR_TEXT


def _run_worker(monkeypatch, events=None, raises=None):
    def fake_stream(*a, **k):
        if raises:
            raise raises
        return iter(events)
    monkeypatch.setattr(llm_client.window_capture, "capture_context_images_b64", lambda: [])
    monkeypatch.setattr(llm_client.state_capture, "capture_ax_state", lambda: None)
    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)
    worker = llm_client.StreamWorker("add a compressor", None)
    errors, done = [], []
    worker.error.connect(errors.append)
    worker.done.connect(lambda *a: done.append(a))
    worker.run()
    return errors, done


def test_stream_error_text_is_shown_as_is(monkeypatch):
    errors, done = _run_worker(monkeypatch, [("error", ERROR_TEXT["down"])])
    assert errors == [ERROR_TEXT["down"]] and done == []


def test_unexpected_exception_shows_retry_and_prints_raw(monkeypatch, capsys):
    errors, done = _run_worker(monkeypatch, raises=RuntimeError("boom in the parser"))
    assert errors == [ERROR_TEXT["retry"]] and done == []
    assert "boom in the parser" in capsys.readouterr().out


def test_successful_turn_emits_no_error(monkeypatch):
    errors, done = _run_worker(monkeypatch, [("chunk", "hi"), ("done", {"event_id": "e1", "remaining": 5})])
    assert errors == []
    assert done and done[0][0] == "e1"
