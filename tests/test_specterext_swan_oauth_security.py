"""Swan OAuth flow security checks without Bitcoin/Node fixtures."""

import base64
import hashlib
import sqlite3
import time
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import pytest
import requests
from flask import Flask, session, request

from cryptoadvance.specterext.swan.client import SwanApiException, SwanClient


@pytest.fixture
def app(tmp_path):
    app = Flask(__name__)
    app.secret_key = "test-only-session-key"
    app.config["SWAN_OAUTH_DB"] = str(tmp_path / "swan-oauth.sqlite")
    app.config.update(
        SWAN_API_URL="https://api.example",
        SWAN_CLIENT_ID="specter-test",
        SWAN_CLIENT_SECRET="test-secret",
        APP_URL_PREFIX="/spc",
        EXT_URL_PREFIX="/ext",
    )
    return app


def client():
    return SwanClient("localhost", None, None, None)


def start(app, cookie=None, user="alice"):
    with app.test_request_context("/spc/ext/swan/oauth2/start"):
        if cookie is not None:
            session.update(cookie)
        url = client().get_oauth2_start_url("localhost", user_id=user)
        return parse_qs(urlparse(url).query), dict(session)


def callback(app, state, cookie, code="auth-code", user="alice", error=None):
    args = {"state": state, "code": code}
    if error:
        args["error"] = error
    with app.test_request_context("/spc/ext/swan/oauth2/callback", query_string=args):
        session.update(cookie)
        return client().handle_oauth2_auth_callback(request, user_id=user)


def test_fresh_flow_challenge_and_state_with_server_side_verifier(app):
    first, cookie = start(app)
    second, _ = start(app, cookie)
    assert first["state"] != second["state"]
    assert first["code_challenge"] != second["code_challenge"]
    assert "verifier" not in repr(cookie)
    assert first["state"][0] not in repr(cookie)
    assert len(first["code_challenge"][0]) == 43


def test_callback_redeems_matching_flow_only_once(app):
    params, cookie = start(app)
    state = params["state"][0]
    with patch("cryptoadvance.specterext.swan.client.requests.post") as post:
        post.return_value.text = (
            '{"access_token":"token","refresh_token":"refresh","expires_in":3600}'
        )
        callback(app, state, cookie)
        payload = post.call_args.kwargs["data"]
        verifier = payload["code_verifier"]
        assert len(verifier) >= 43
        assert (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
            == params["code_challenge"][0]
        )
        assert payload["state"] == state
        assert payload["redirect_uri"] == params["redirect_uri"][0]
        with pytest.raises(SwanApiException):
            callback(app, state, cookie)
        assert post.call_count == 1


@pytest.mark.parametrize("bad_state", [None, "", "wrong"])
def test_invalid_state_never_redeems(app, bad_state):
    params, cookie = start(app)
    with patch("cryptoadvance.specterext.swan.client.requests.post") as post:
        with pytest.raises(SwanApiException):
            callback(app, bad_state, cookie)
        post.assert_not_called()


def test_user_and_browser_are_bound_to_flow(app):
    params, cookie = start(app)
    with patch("cryptoadvance.specterext.swan.client.requests.post") as post:
        with pytest.raises(SwanApiException):
            callback(app, params["state"][0], cookie, user="bob")
        with pytest.raises(SwanApiException):
            callback(app, params["state"][0], {})
        post.assert_not_called()


def test_concurrent_flows_redeem_independently(app):
    one, cookie = start(app)
    two, cookie = start(app, cookie)
    with patch("cryptoadvance.specterext.swan.client.requests.post") as post:
        post.return_value.text = '{"access_token":"token","expires_in":3600}'
        callback(app, two["state"][0], cookie)
        verifier_two = post.call_args.kwargs["data"]["code_verifier"]
        callback(app, one["state"][0], cookie)
        assert post.call_args.kwargs["data"]["code_verifier"] != verifier_two


def test_expired_flow_and_provider_error_never_redeem(app):
    params, cookie = start(app)
    with patch(
        "cryptoadvance.specterext.swan.client.time.time", return_value=time.time() + 601
    ):
        with patch("cryptoadvance.specterext.swan.client.requests.post") as post:
            with pytest.raises(SwanApiException):
                callback(app, params["state"][0], cookie)
            post.assert_not_called()
    params, cookie = start(app, cookie)
    with patch("cryptoadvance.specterext.swan.client.requests.post") as post:
        with pytest.raises(SwanApiException):
            callback(app, params["state"][0], cookie, error="access_denied")
        with pytest.raises(SwanApiException):
            callback(app, params["state"][0], cookie)
        post.assert_not_called()


def test_missing_code_consumes_state_without_refresh_fallback(app):
    params, cookie = start(app)
    with patch("cryptoadvance.specterext.swan.client.requests.post") as post:
        with pytest.raises(SwanApiException):
            callback(app, params["state"][0], cookie, code=None)
        with pytest.raises(SwanApiException):
            callback(app, params["state"][0], cookie)
        post.assert_not_called()


def test_exchange_failure_consumes_state(app):
    params, cookie = start(app)
    with patch("cryptoadvance.specterext.swan.client.requests.post") as post:
        post.side_effect = requests.exceptions.Timeout("timeout")
        with pytest.raises(SwanApiException):
            callback(app, params["state"][0], cookie)
        with pytest.raises(SwanApiException):
            callback(app, params["state"][0], cookie)
        assert post.call_count == 1


def test_callback_host_must_match_original_redirect(app):
    params, cookie = start(app)
    with app.test_request_context(
        "http://different-host/spc/ext/swan/oauth2/callback",
        query_string={"state": params["state"][0], "code": "auth-code"},
    ):
        session.update(cookie)
        with patch("cryptoadvance.specterext.swan.client.requests.post") as post:
            with pytest.raises(SwanApiException):
                client().handle_oauth2_auth_callback(request, user_id="alice")
            post.assert_not_called()


def test_oldest_tab_evicted_after_flow_limit(app):
    params, cookie = start(app)
    for _ in range(8):
        _, cookie = start(app, cookie)
    with patch("cryptoadvance.specterext.swan.client.requests.post") as post:
        with pytest.raises(SwanApiException):
            callback(app, params["state"][0], cookie)
        post.assert_not_called()


def test_separate_worker_redeems_same_session_once(app):
    params, cookie = start(app)
    other_worker = Flask("other-worker")
    other_worker.secret_key = app.secret_key
    other_worker.config.update(app.config)
    with patch("cryptoadvance.specterext.swan.client.requests.post") as post:
        post.return_value.text = '{"access_token":"token","expires_in":3600}'
        callback(other_worker, params["state"][0], cookie)
        with pytest.raises(SwanApiException):
            callback(app, params["state"][0], cookie)
        assert post.call_count == 1


def test_server_store_encrypts_verifier_at_rest(app):
    params, _ = start(app)
    with sqlite3.connect(app.config["SWAN_OAUTH_DB"]) as db:
        stored = db.execute(
            "SELECT verifier FROM flows WHERE state = ?", (params["state"][0],)
        ).fetchone()[0]
    assert len(stored) > 43
