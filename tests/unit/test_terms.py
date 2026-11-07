"""Glossary term spans from the server become term links in the reply, and survive a session reload."""
from core.state.conversation import Conversation
from ui.message.terms import terms_html, valid_terms

TEXT = "Raise the buffer size.\nLatency <goes> up."


def _t(start, end, **kw):
    return {"start": start, "end": end, "term": "x", "definition": "d", **kw}


def test_valid_terms_drops_bad_spans() -> None:
    good = _t(10, 21)
    terms = [_t(23, 30), good, _t(15, 25), _t(5, 999), {"start": 1, "end": 2}, "junk", _t(3, 3)]
    assert valid_terms(TEXT, terms) == [good, _t(23, 30)]


def test_terms_html_links_escapes_and_keeps_breaks() -> None:
    html = terms_html(TEXT, valid_terms(TEXT, [_t(10, 21)]))
    assert '<a href="term:0"' in html and ">buffer size</a>" in html
    assert "&lt;goes&gt;" in html and "white-space: pre-wrap" in html


def test_terms_round_trip_through_saved_messages() -> None:
    conv = Conversation()
    conv.load_messages([{"role": "assistant", "text": TEXT, "terms": [_t(10, 21)]},
                        {"role": "assistant", "text": "old save, no terms"}])
    assert conv.messages()[0].terms == [_t(10, 21)] and conv.messages()[1].terms == []
