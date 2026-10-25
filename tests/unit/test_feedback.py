"""Report Bug: the log tee, the recent-context ring, the context dump and the POST body."""
import io

from core.net import feedback
from core.state import recent_context, run_log


def test_tee_keeps_whole_lines_and_forwards(monkeypatch):
    monkeypatch.setattr(run_log, "_lines", run_log.deque(maxlen=3))
    out = io.StringIO()
    tee = run_log._Tee(out)
    tee.write("[wt] step 1\n[wt] st")
    tee.write("ep 2\n")
    for i in range(3):
        tee.write(f"line {i}\n")
    assert out.getvalue().startswith("[wt] step 1\n[wt] step 2\n")
    lines = run_log.tail().splitlines()
    assert [ln.split(" ", 1)[1] for ln in lines] == ["line 0", "line 1", "line 2"], lines


def test_tee_survives_no_console():
    """The packaged app has sys.stdout None; the tee still records."""
    run_log._Tee(None).write("[conductor] packaged\n")
    assert run_log.tail().endswith("[conductor] packaged")


def test_recent_context_keeps_the_last_ax_states():
    recent_context.clear()
    for i in range(recent_context.MAX_AX_STATES + 2):
        recent_context.note_ax_state(f"ax {i}", f"msg {i}")
    texts = [a["text"] for a in recent_context.ax_states()]
    assert texts == [f"ax {i}" for i in range(2, recent_context.MAX_AX_STATES + 2)], texts


def test_build_context_has_everything(monkeypatch):
    recent_context.clear()
    recent_context.note_ax_state("turn ax", "add a compressor")
    recent_context.note_card([{"kind": "menu"}])
    monkeypatch.setattr(feedback.state_capture, "capture_ax_state", lambda: "fresh ax")
    monkeypatch.setattr(feedback, "logic_version", lambda: "11.2")
    chat = [{"role": "user", "text": "hi"}]
    ctx = feedback.build_context(chat, [{"role": "user"}])
    assert ctx["chat"] == chat and ctx["server_history"] == [{"role": "user"}]
    assert [a["text"] for a in ctx["ax_states"]] == ["turn ax", "fresh ax"]
    assert ctx["card"]["steps"] == [{"kind": "menu"}]
    assert ctx["versions"]["logic"] == "11.2" and ctx["versions"]["conductor"] == feedback.VERSION
    assert isinstance(ctx["run_log"], str)


class _Resp:
    def __init__(self, status):
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_post_body_and_401_retry(monkeypatch):
    calls, statuses = [], [401, 200]
    monkeypatch.setattr(feedback, "ensure_token", lambda: "tok")
    monkeypatch.setattr(feedback.identity, "clear_token", lambda: None)
    monkeypatch.setattr(feedback.httpx, "post",
                        lambda url, headers, json, timeout: calls.append(json) or _Resp(statuses.pop(0)))
    feedback.post_feedback("feedback", "Love it", "", None)
    assert len(calls) == 2, calls
    assert calls[0] == {"kind": "feedback", "title": "Love it", "message": "",
                        "app_version": feedback.VERSION, "context": None}


def test_worker_without_context_skips_capture(monkeypatch):
    sent = []
    monkeypatch.setattr(feedback, "build_context", lambda *a: (_ for _ in ()).throw(AssertionError("captured")))
    monkeypatch.setattr(feedback, "post_feedback", lambda *a: sent.append(a))
    w = feedback.FeedbackWorker("feedback", "t", "", None, None)
    w.run()
    assert sent == [("feedback", "t", "", None)]
