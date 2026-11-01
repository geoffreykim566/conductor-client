"""Register with the waitlist gate: the email is sent, a 403 becomes RegistrationRefused with its reason, and each reason has its own text."""
from unittest.mock import patch

import httpx
import pytest

from core.net import auth


def _resp(status: int, body: dict) -> httpx.Response:
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://x/v3/register"))


def test_email_is_sent_and_token_saved() -> None:
    with patch.object(auth.httpx, "post", return_value=_resp(200, {"conductor_id": "u.sig"})) as post, \
            patch.object(auth.identity, "save_token") as save:
        assert auth.register("a@b.co") == "u.sig"
    assert post.call_args.kwargs["json"] == {"email": "a@b.co"}
    save.assert_called_once_with("u.sig")


def test_no_email_sends_no_body() -> None:
    with patch.object(auth.httpx, "post", return_value=_resp(200, {"conductor_id": "u.sig"})) as post, \
            patch.object(auth.identity, "save_token"):
        auth.register()
    assert post.call_args.kwargs["json"] is None


@pytest.mark.parametrize("reason", ["email_required", "not_on_waitlist", "not_approved", "install_limit"])
def test_403_raises_with_the_reason(reason) -> None:
    with patch.object(auth.httpx, "post", return_value=_resp(403, {"detail": reason})), \
            patch.object(auth.identity, "save_token") as save:
        with pytest.raises(auth.RegistrationRefused) as e:
            auth.register("a@b.co")
    assert e.value.reason == reason
    save.assert_not_called()


def test_each_reason_has_its_own_text() -> None:
    from ui.onboarding.email_screen import refusal_text
    texts = {r: refusal_text(r) for r in ["email_required", "not_on_waitlist", "not_approved", "install_limit"]}
    assert len(set(texts.values())) == 4, texts
    assert refusal_text("something_new") == texts["email_required"]
