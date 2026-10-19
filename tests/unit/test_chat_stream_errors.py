"""stream_chat: each way a turn can fail maps to one of the four user texts; the raw cause is printed."""
import json

import httpx
import pytest

from core.net import chat_stream
from core.net.chat_stream import ERROR_TEXT


def _stream(monkeypatch, handler) -> list:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(chat_stream, "ensure_token", lambda: "t")
    monkeypatch.setattr(chat_stream, "headers", lambda t: {})
    monkeypatch.setattr(chat_stream.httpx, "stream", lambda method, url, **kw: client.stream(method, url, **kw))
    return list(chat_stream.stream_chat("hi", None, [], None))


def _sse(*events) -> httpx.Response:
    return httpx.Response(200, text="".join(f"data: {json.dumps(e)}\n\n" for e in events))


@pytest.mark.parametrize("response, kind", [
    (httpx.Response(429, json={"error": "Rate limit exceeded: 10 per 1 minute"}), "busy"),
    (httpx.Response(503, json={"detail": {"error": "free_tier_paused"}}), "down"),
    (_sse({"type": "error", "kind": "down", "message": "x"}), "down"),
    (_sse({"type": "error", "kind": "busy", "message": "x"}), "busy"),
    (_sse({"type": "error", "message": "HTTPStatusError: 401 for api.openai.com"}), "retry"),  # older server
])
def test_failures_map_to_user_text(monkeypatch, capsys, response, kind):
    events = _stream(monkeypatch, lambda req: response)
    assert events == [("error", ERROR_TEXT[kind])], events
    assert "[server_error]" in capsys.readouterr().out


def test_connect_error_is_offline(monkeypatch):
    def refuse(req):
        raise httpx.ConnectError("nodename nor servname provided", request=req)
    assert _stream(monkeypatch, refuse) == [("error", ERROR_TEXT["offline"])]
