"""Plug-in reads on the wire: every request offers reads, a parked read reaches the UI as
plugin_read_prompt, and a resume carries the read values."""
import json

import httpx

from core.net import chat_stream, llm_client


def _capture(monkeypatch, response_events, **kwargs):
    sent = []

    def handler(req):
        sent.append(json.loads(req.content))
        return httpx.Response(200, text="".join(f"data: {json.dumps(e)}\n\n" for e in response_events))
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(chat_stream, "ensure_token", lambda: "t")
    monkeypatch.setattr(chat_stream, "headers", lambda t: {})
    monkeypatch.setattr(chat_stream.httpx, "stream", lambda method, url, **kw: client.stream(method, url, **kw))
    return list(chat_stream.stream_chat("hi", None, [], None, **kwargs)), sent


def test_parked_read_ends_the_stream(monkeypatch):
    prompt = {"type": "plugin_read_prompt", "plugin": "Compressor", "track": "Vocal", "history": [{"x": 1}]}
    events, sent = _capture(monkeypatch, [prompt, {"type": "done"}])
    assert events == [("plugin_read_prompt", prompt)], events
    assert sent[0]["plugin_reads"] is True and sent[0]["plugin_values"] is None


def test_resume_sends_the_values(monkeypatch):
    values = {"plugin": "Compressor", "values": {"Threshold": "-20.0 dB"}}
    _, sent = _capture(monkeypatch, [{"type": "done"}], resume="allow_plugin_read", plugin_values=values)
    assert sent[0]["resume"] == "allow_plugin_read" and sent[0]["plugin_values"] == values


def test_worker_emits_the_read_prompt(monkeypatch):
    monkeypatch.setattr(llm_client.window_capture, "capture_context_images_b64", lambda: [])
    monkeypatch.setattr(llm_client.state_capture, "capture_ax_state", lambda: None)
    monkeypatch.setattr(llm_client, "stream_chat", lambda *a, **k: iter([
        ("plugin_read_prompt", {"plugin": "Compressor", "track": None, "history": ["h"]})]))
    worker = llm_client.StreamWorker("what are my settings", None)
    got, done = [], []
    worker.plugin_read_prompt.connect(lambda *a: got.append(a))
    worker.done.connect(lambda *a: done.append(a))
    worker.run()
    assert got == [("Compressor", None, ["h"])] and done == [], (got, done)
