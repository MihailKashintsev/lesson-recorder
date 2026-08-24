"""Regression test: a user hit a GigaChat 401 Unauthorized and the app only
showed them the raw requests exception text ("401 Client Error: Unauthorized
for url: ..."), with zero guidance on what to actually do about it. The
token-fetch logic itself was also duplicated between core/summarizer.py and
ui/settings_widget.py's "Test connection" button — both showing that same
unhelpful raw text. Consolidated into fetch_gigachat_token(), which raises
GigaChatAuthError with an actionable message for a 401 specifically.
"""
from unittest.mock import MagicMock, patch

import requests

from core.summarizer import fetch_gigachat_token, GigaChatAuthError, Summarizer


def _response(status_code, json_body=None):
    r = MagicMock(spec=requests.Response)
    r.status_code = status_code
    r.json.return_value = json_body or {}
    if status_code >= 400:
        err = requests.exceptions.HTTPError(response=r)
        r.raise_for_status.side_effect = err
    else:
        r.raise_for_status.return_value = None
    return r


@patch("core.summarizer.requests.post")
def test_401_raises_actionable_gigachat_auth_error(mock_post):
    mock_post.return_value = _response(401)

    try:
        fetch_gigachat_token("bad-key")
        assert False, "expected GigaChatAuthError"
    except GigaChatAuthError as e:
        msg = str(e)
        assert "401" in msg
        assert "developers.sber.ru" in msg
        # not just the raw exception repr — real guidance
        assert "Authorization key" in msg


@patch("core.summarizer.requests.post")
def test_other_http_error_still_raises_gigachat_auth_error(mock_post):
    mock_post.return_value = _response(500)

    try:
        fetch_gigachat_token("some-key")
        assert False, "expected GigaChatAuthError"
    except GigaChatAuthError as e:
        assert "500" in str(e)


@patch("core.summarizer.requests.post")
def test_network_failure_raises_gigachat_auth_error(mock_post):
    mock_post.side_effect = requests.exceptions.ConnectionError("no route to host")

    try:
        fetch_gigachat_token("some-key")
        assert False, "expected GigaChatAuthError"
    except GigaChatAuthError as e:
        assert "связаться" in str(e)


@patch("core.summarizer.requests.post")
def test_success_returns_access_token(mock_post):
    mock_post.return_value = _response(200, {"access_token": "abc123"})

    assert fetch_gigachat_token("good-key") == "abc123"


@patch("core.summarizer.requests.post")
def test_400_raises_scope_mismatch_guidance(mock_post):
    """A real user hit exactly this: 400 Bad Request, not 401 — the request
    reached Sber's server and was structurally fine, but the scope
    (GIGACHAT_API_PERS/B2B/CORP) didn't match their actual project type."""
    mock_post.return_value = _response(400)

    try:
        fetch_gigachat_token("some-key", scope="GIGACHAT_API_PERS")
        assert False, "expected GigaChatAuthError"
    except GigaChatAuthError as e:
        msg = str(e)
        assert "400" in msg
        assert "GIGACHAT_API_PERS" in msg
        assert "тип аккаунта" in msg.lower()


@patch("core.summarizer.requests.post")
def test_scope_is_actually_sent_in_the_request_body(mock_post):
    mock_post.return_value = _response(200, {"access_token": "tok"})

    fetch_gigachat_token("some-key", scope="GIGACHAT_API_B2B")

    _, kwargs = mock_post.call_args
    assert kwargs["data"] == {"scope": "GIGACHAT_API_B2B"}


@patch("core.summarizer.requests.post")
def test_default_scope_is_personal(mock_post):
    mock_post.return_value = _response(200, {"access_token": "tok"})

    fetch_gigachat_token("some-key")

    _, kwargs = mock_post.call_args
    assert kwargs["data"] == {"scope": "GIGACHAT_API_PERS"}


@patch("core.summarizer.requests.post")
def test_summarizer_threads_its_configured_scope_through(mock_post):
    mock_post.return_value = _response(200, {"access_token": "tok"})

    s = Summarizer(
        transcript="test", provider="gigachat", api_key="k",
        model="GigaChat", gigachat_scope="GIGACHAT_API_CORP",
    )
    assert s._get_gigachat_token() == "tok"

    _, kwargs = mock_post.call_args
    assert kwargs["data"] == {"scope": "GIGACHAT_API_CORP"}
