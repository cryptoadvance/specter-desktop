import re
import sys
from uuid import uuid4

import pytest

from cryptoadvance.specter.config import TestConfig
from cryptoadvance.specter.helpers import hwi_get_config
from cryptoadvance.specter.server import create_app, init_app
from cryptoadvance.specter.specter import Specter


def make_scoped_app(tmp_path, hwibridge, auth_method="none"):
    config_name = f"ScopedTestConfig_{uuid4().hex}"
    config_class = type(
        config_name,
        (TestConfig,),
        {
            "__module__": __name__,
            "SPECTER_DATA_FOLDER": str(tmp_path),
            "SPECTER_URL_PREFIX": "/spc",
            "SESSION_COOKIE_PATH": "/spc",
            "SESSION_PROTECTION": None,
            "SKIP_HWI_INITIALISATION_AT_STARTUP": True,
            "SPECTER_API_ACTIVE": False,
        },
    )
    setattr(sys.modules[__name__], config_name, config_class)
    specter = Specter(data_folder=str(tmp_path), checker_threads=False)
    if auth_method != "none":
        specter.update_auth(auth_method, 10, 1)

    app = create_app(config_class)
    app.config["TESTING"] = True
    with app.app_context():
        init_app(app, hwibridge=hwibridge, specter=specter)
    return app


def csrf_token(response):
    match = re.search(b'name="csrf_token" value="([^"]+)', response.data)
    assert match is not None
    return match.group(1).decode()


@pytest.mark.parametrize("hwibridge", [False, True])
def test_hwi_settings_use_session_scoped_route(tmp_path, hwibridge):
    app = make_scoped_app(tmp_path, hwibridge)
    client = app.test_client()

    legacy_response = client.get("/hwi/settings/")
    assert legacy_response.status_code == 302
    assert legacy_response.headers["Location"] == "/spc/hwi/settings/"

    settings_response = client.get("/spc/hwi/settings/")
    assert settings_response.status_code == 200
    assert "Path=/spc" in settings_response.headers["Set-Cookie"]

    missing_csrf_response = client.post(
        "/spc/hwi/settings/",
        data={"action": "update", "whitelisted_domains": "http://attacker/"},
    )
    assert missing_csrf_response.status_code in (302, 400)
    assert hwi_get_config(app.specter)["whitelisted_domains"] != "http://attacker/"

    invalid_csrf_response = client.post(
        "/spc/hwi/settings/",
        data={
            "action": "update",
            "csrf_token": "invalid",
            "whitelisted_domains": "http://attacker/",
        },
    )
    assert invalid_csrf_response.status_code in (302, 400)
    assert hwi_get_config(app.specter)["whitelisted_domains"] != "http://attacker/"

    update_response = client.post(
        "/spc/hwi/settings/",
        data={
            "action": "update",
            "csrf_token": csrf_token(settings_response),
            "whitelisted_domains": "http://example.com/",
        },
    )
    assert update_response.status_code == 200
    assert (
        hwi_get_config(app.specter)["whitelisted_domains"].strip()
        == "http://example.com/"
    )


@pytest.mark.parametrize("hwibridge", [False, True])
def test_hwi_settings_require_authenticated_admin(tmp_path, hwibridge):
    app = make_scoped_app(tmp_path, hwibridge=hwibridge, auth_method="usernamepassword")
    client = app.test_client()

    anonymous_response = client.get("/spc/hwi/settings/")
    assert anonymous_response.status_code == 302
    assert anonymous_response.headers["Location"].startswith(
        "/spc/auth/login?next=%2Fspc%2Fhwi%2Fsettings%2F"
    )
    assert client.get("/spc/auth/login").status_code == 200

    login_response = client.post(
        "/spc/auth/login",
        data={
            "username": "admin",
            "password": "admin",
            "next": "/spc/hwi/settings/",
        },
    )
    assert login_response.status_code == 302
    assert login_response.headers["Location"] == "/spc/hwi/settings/"
    assert client.get(login_response.headers["Location"]).status_code == 200

    app.specter.user_manager.create_user(
        user_id="nonadmin",
        username="nonadmin",
        plaintext_password="nonadmin",
        config={},
    )
    nonadmin_client = app.test_client()
    nonadmin_login_response = nonadmin_client.post(
        "/spc/auth/login",
        data={
            "username": "nonadmin",
            "password": "nonadmin",
            "next": "/spc/hwi/settings/",
        },
    )
    assert nonadmin_login_response.status_code == 302
    assert nonadmin_client.get("/spc/hwi/settings/").status_code == 403


def test_hwi_settings_force_admin_when_login_disabled(tmp_path):
    app = make_scoped_app(tmp_path, hwibridge=True, auth_method="usernamepassword")
    app.specter.user_manager.create_user(
        user_id="nonadmin",
        username="nonadmin",
        plaintext_password="nonadmin",
        config={},
    )
    client = app.test_client()
    login_response = client.post(
        "/spc/auth/login",
        data={
            "username": "nonadmin",
            "password": "nonadmin",
            "next": "/spc/hwi/settings/",
        },
    )
    assert login_response.status_code == 302

    app.specter.update_auth("none", 10, 1)
    app.config["LOGIN_DISABLED"] = True
    assert client.get("/spc/hwi/settings/").status_code == 200
    with client.session_transaction(path="/spc/hwi/settings/") as session:
        assert session["_user_id"] == "admin"


@pytest.mark.parametrize("hwibridge", [False, True])
def test_hwi_api_remains_csrf_exempt(tmp_path, hwibridge):
    app = make_scoped_app(tmp_path, hwibridge=hwibridge)
    app.specter.hwi.exposed_rpc["enumerate"] = lambda **kwargs: []
    client = app.test_client()
    client.environ_base["HTTP_ORIGIN"] = "http://127.0.0.1:25441/"

    response = client.post(
        "/hwi/api/",
        json={
            "jsonrpc": "2.0",
            "method": "enumerate",
            "id": 1,
            "params": {},
            "forwarded_request": True,
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {"id": 1, "jsonrpc": "2.0", "result": []}
