"""Swan OAuth flow security checks without Bitcoin/Node fixtures."""

import base64
import hashlib
import importlib.util
import os
import sqlite3
import stat
import time
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from unittest.mock import MagicMock, patch

import pytest
import requests
from flask import Blueprint, Flask, session, request
from flask_login import LoginManager, UserMixin

from cryptoadvance.specterext.swan.client import SwanApiException, SwanClient


@pytest.fixture
def app(tmp_path):
    app = Flask(
        __name__,
        template_folder=str(
            Path(__file__).resolve().parents[1]
            / "src/cryptoadvance/specterext/swan/templates"
        ),
    )
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


class RefreshTarget(HTMLParser):
    def __init__(self):
        super().__init__()
        self.target = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("http-equiv") == "refresh":
            content = attrs.get("content")
            if content is not None:
                self.target = content.split(";url=", 1)[1]


def register_oauth_routes(app, monkeypatch):
    """Load a private controller copy so this isolated app cannot poison the real blueprint."""
    from cryptoadvance.specterext.swan.service import SwanService

    bp = Blueprint("swan_endpoint", __name__, url_prefix="/spc/ext/swan")
    monkeypatch.setattr(SwanService, "blueprint", bp, raising=False)
    path = (
        Path(__file__).resolve().parents[1]
        / "src/cryptoadvance/specterext/swan/controller.py"
    )
    spec = importlib.util.spec_from_file_location(
        "cryptoadvance.specterext.swan._oauth_test_controller", path
    )
    assert spec is not None and spec.loader is not None
    controller = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controller)
    app.register_blueprint(bp)
    return SwanService


def start(app, cookie=None, user="alice", scheme="http"):
    with app.test_request_context(f"{scheme}://localhost/spc/ext/swan/oauth2/start"):
        if cookie is not None:
            session.update(cookie)
        url = client().get_oauth2_start_url("localhost", user_id=user)
        return parse_qs(urlparse(url).query), dict(session)


def callback(
    app, state, cookie, code="auth-code", user="alice", error=None, scheme="http"
):
    args = {"state": state, "code": code}
    if error:
        args["error"] = error
    with app.test_request_context(
        f"{scheme}://localhost/spc/ext/swan/oauth2/callback", query_string=args
    ):
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
    other_worker = Flask(__name__)
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


def test_https_flow_uses_exact_registered_callback_for_exchange(app):
    params, cookie = start(app, scheme="https")
    assert params["redirect_uri"] == ["https://localhost/spc/ext/swan/oauth2/callback"]
    with patch("cryptoadvance.specterext.swan.client.requests.post") as post:
        post.return_value.text = '{"access_token":"token","expires_in":3600}'
        callback(app, params["state"][0], cookie, scheme="https")
        assert (
            post.call_args.kwargs["data"]["redirect_uri"] == params["redirect_uri"][0]
        )


def test_existing_world_readable_store_and_parent_are_restricted(app):
    path = app.config["SWAN_OAUTH_DB"]
    with open(path, "wb"):
        pass
    os.chmod(path, 0o644)
    os.chmod(os.path.dirname(path), 0o755)
    start(app)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode) == 0o700


def test_store_rejects_symlink_to_another_database(app, tmp_path):
    target = tmp_path / "other.sqlite"
    target.write_bytes(b"private data")
    os.symlink(target, app.config["SWAN_OAUTH_DB"])
    with pytest.raises(OSError):
        start(app)
    assert target.read_bytes() == b"private data"


def test_store_restricts_existing_sidecars(app):
    path = app.config["SWAN_OAUTH_DB"]
    start(app)
    sidecar = path + "-shm"
    with open(sidecar, "wb"):
        pass
    os.chmod(sidecar, 0o644)
    start(app)
    assert stat.S_IMODE(os.stat(sidecar).st_mode) == 0o600


def test_store_rejects_symlinked_parent(app, tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    app.config["SWAN_OAUTH_DB"] = str(link / "swan-oauth.sqlite")
    with pytest.raises(OSError):
        start(app)
    assert not (real / "swan-oauth.sqlite").exists()


def test_strict_cookie_callback_lands_without_cookie_then_completes_same_site(
    app, monkeypatch
):
    SwanService = register_oauth_routes(app, monkeypatch)
    app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
    app.add_url_rule(
        "/cookie-check", view_func=lambda: session.__setitem__("touched", True) or "ok"
    )
    login = LoginManager(app)

    class TestUser(UserMixin):
        id = "alice"

    @login.user_loader
    def load_user(user_id):
        return TestUser() if user_id == "alice" else None

    params, cookie = start(app, scheme="https")
    state = params["state"][0]
    path = f"/spc/ext/swan/oauth2/callback?state={state}&code=auth-code"
    no_cookie = app.test_client(use_cookies=False)
    with patch("cryptoadvance.specterext.swan.client.requests.post") as post:
        landing = no_cookie.get(path, base_url="https://localhost")
        assert landing.status_code == 200
        assert landing.headers["Cache-Control"] == "no-store"
        assert (
            landing.headers["Content-Security-Policy"]
            == "default-src 'none'; base-uri 'none'"
        )
        refresh = RefreshTarget()
        refresh.feed(landing.get_data(as_text=True))
        assert (
            refresh.target
            == f"/spc/ext/swan/oauth2/complete?state={state}&code=auth-code"
        )
        assert (
            no_cookie.get(
                f"/spc/ext/swan/oauth2/complete?state={state}&code=auth-code",
                base_url="https://localhost",
            ).status_code
            == 401
        )
        post.assert_not_called()

        same_site = app.test_client()
        with same_site.session_transaction() as browser_session:
            browser_session.update(cookie)
            browser_session["_user_id"] = "alice"
            browser_session["_fresh"] = True
        assert "SameSite=Strict" in same_site.get("/cookie-check").headers["Set-Cookie"]
        fake_user = MagicMock()
        app.specter = SimpleNamespace(
            user_manager=SimpleNamespace(get_user=lambda: fake_user)
        )
        post.return_value.text = '{"access_token":"token","expires_in":3600}'
        with (
            patch.object(SwanService, "client", side_effect=client),
            patch.object(SwanService, "store_new_api_access_data"),
            patch.object(SwanService, "sync_swan_data"),
            patch.object(SwanService, "get_current_user_service_data", return_value={}),
        ):
            completed = same_site.get(refresh.target, base_url="https://localhost")
        assert completed.status_code == 302
        assert completed.location.endswith("/spc/ext/swan/oauth2/success")
        assert (
            post.call_args.kwargs["data"]["redirect_uri"] == params["redirect_uri"][0]
        )
        assert fake_user.add_service.call_count == 1


def test_landing_never_reflects_query_as_html_or_external_redirect(app, monkeypatch):
    register_oauth_routes(app, monkeypatch)
    response = app.test_client(use_cookies=False).get(
        '/spc/ext/swan/oauth2/callback?code=<script>&next=https://evil.example/;url=https://evil.example&html="<img src=x onerror=alert(1)>',
    )
    assert response.status_code == 200
    assert b"<script>" not in response.data
    assert b"<img" not in response.data
    assert b"&quot;" in response.data or b"%22" in response.data
    assert b";url=https://evil.example" not in response.data
    assert b"/spc/ext/swan/oauth2/complete?" in response.data
