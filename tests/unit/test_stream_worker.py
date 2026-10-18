"""StreamWorker: a server-side turn failure reaches the user as one fixed message."""
from core.net import llm_client


def _run_worker(monkeypatch, events):
    monkeypatch.setattr(llm_client.window_capture, "capture_context_images_b64", lambda: [])
    monkeypatch.setattr(llm_client.state_capture, "capture_ax_state", lambda: None)
    monkeypatch.setattr(llm_client, "stream_chat", lambda *a, **k: iter(events))
    worker = llm_client.StreamWorker("add a compressor", None)
    errors, done = [], []
    worker.error.connect(errors.append)
    worker.done.connect(lambda *a: done.append(a))
    worker.run()
    return errors, done


def test_server_error_shows_unavailable_not_raw_text(monkeypatch, capsys):
    raw = "HTTPStatusError: Client error '401 Unauthorized' for url 'https://api.openai.com/v1/responses'"
    errors, done = _run_worker(monkeypatch, [("error", raw)])
    assert errors == [llm_client.ASSISTANT_UNAVAILABLE]
    assert "API key" not in errors[0]
    assert done == []
    assert raw in capsys.readouterr().out


def test_successful_turn_emits_no_error(monkeypatch):
    errors, done = _run_worker(monkeypatch, [("chunk", "hi"), ("done", {"event_id": "e1", "remaining": 5})])
    assert errors == []
    assert done and done[0][0] == "e1"
