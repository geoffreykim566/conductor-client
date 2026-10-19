"""stream_chat: each way a turn can fail maps to one of the four user texts; the raw cause is printed."""
import json

import httpx
import pytest

from core.net import chat_stream
from core.net.chat_stream import ERROR_TEXT, error_text


def _stream(monkeypatch, handler) -> list:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(chat_stream, "ensure_token", lambda: "t")
    monkeypatch.setattr(chat_stream, "headers", lambda t: {})
    monkeypatch.setattr(chat_stream.httpx, "stream", lambda method, url, **kw: client.stream(method, url, **kw))
    return list(chat_stream.stream_chat("hi", None, [], None))


def _sse(*events) -> httpx.Response:
    return httpx.Response(200, text="".join(f"data: {json.dumps(e)}\n\n" for e in events))


@pytest.mark.parametrize("response, shown", [
    (httpx.Response(429, json={"error": "Rate limit exceeded: 10 per 1 minute"}), "[Error 429] " + ERROR_TEXT["busy"]),
    (httpx.Response(503, json={"detail": {"error": "free_tier_paused"}}), "[Error 503] " + ERROR_TEXT["down"]),
    (_sse({"type": "error", "kind": "down", "code": 401, "message": "x"}), "[Error 401] " + ERROR_TEXT["down"]),
    (_sse({"type": "error", "kind": "down", "code": None, "message": "x"}), "[Error] " + ERROR_TEXT["down"]),
    (_sse({"type": "error", "kind": "busy", "code": 429, "message": "x"}), "[Error 429] " + ERROR_TEXT["busy"]),
    (_sse({"type": "error", "message": "HTTPStatusError: 401 for api.openai.com"}), "[Error] " + ERROR_TEXT["retry"]),  # older server
])
def test_failures_map_to_user_text(monkeypatch, capsys, response, shown):
    events = _stream(monkeypatch, lambda req: response)
    assert events == [("error", shown)], events
    assert "[server_error]" in capsys.readouterr().out


def test_connect_error_is_offline(monkeypatch):
    def refuse(req):
        raise httpx.ConnectError("nodename nor servname provided", request=req)
    assert _stream(monkeypatch, refuse) == [("error", error_text("offline"))]
