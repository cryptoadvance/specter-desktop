import logging
import pytest
import sys
from flask import Blueprint
from cryptoadvance.specter.server import create_app, init_app
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.config import TestConfig
from conftest import specter_app_with_config


@pytest.mark.slow
def test_home(caplog, client):
    """The root of the app"""
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    login(client, "secret")
    result = client.get("/")
    # By default there is no authentication
    assert result.status_code == 302  # REDIRECT.
    result = client.get("/welcome/about")
    assert b"Welcome to Specter" in result.data
    result = client.get("/devices/new_device_type", follow_redirects=True)
    assert result.status_code == 200  # OK.
    assert b"Add Device" in result.data
    result = client.get("/settings", follow_redirects=True)
    assert result.status_code == 200  # OK.
    assert b"Settings" in result.data
    result = client.get("/wallets/new_wallet", follow_redirects=True)
    assert result.status_code == 200  # OK.
    assert b"Select the type of the wallet" in result.data
    logout(client)

    # Login logout testing
    result = client.get("/auth/login", follow_redirects=False)
    assert result.status_code == 200
    assert b"Password" in result.data
    result = login(client, "secret")
    assert b"Logged in successfully." in result.data
    result = logout(client)
    assert b"You were logged out" in result.data
    result = login(client, "non_valid_password")
    assert b"Invalid username or password" in result.data
    result = login(client, "blub")
    assert b"Invalid username or password" in result.data


@pytest.mark.slow
def test_settings_general(caplog, client):
    login(client, "secret")
    result = client.get("/settings/general", follow_redirects=True)
    assert result.status_code == 200  # OK.
    assert b"Network:" in result.data
    assert b"regtest" in result.data


@pytest.mark.slow
def test_settings_general_restore_wallet(bitcoin_regtest, caplog, client):
    login(client, "secret")
    restore_wallets = open(
        "./tests/controller_testdata/restore_wallets.json", "r"
    ).read()
    restore_devices = open(
        "./tests/controller_testdata/restore_devices.json", "r"
    ).read()
    result = client.get("/settings/general", follow_redirects=True)
    assert b"Load Specter backup:" in result.data
    csrf_token = (
        str(result.data)
        .split('<input type="hidden" class="csrf-token" name="csrf_token" value="')[1]
        .split('"')[0]
    )
    result = client.post(
        "/settings/general",
        data=dict(
            action="restore",
            autohide_sensitive_info_timeout="NEVER",
            autologout_timeout="NEVER",
            explorer="CUSTOM",
            custom_explorer="",
            unit="btc",
            fee_estimator="mempool",
            fee_estimator_custom_url="",
            loglevel="debug",
            restoredevices=restore_devices,
            restorewallets=restore_wallets,
            proxy_url="",
            only_tor="off",
            tor_control_port="",
            csrf_token=csrf_token,
        ),
    )
    assert b"Specter data was successfully loaded from backup" in result.data
    assert b"SimpleMyNiceDevice" in result.data
    # assert b'btc Hot Wallet' in result.data # Not sure why this doesn't work
    assert b"myNiceDevice" in result.data
    assert b"btchot" in result.data


def test_APP_URL_PREFIX(caplog):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    myapp = specter_app_with_config(
        config={"APP_URL_PREFIX": "/someprefix", "SPECTER_URL_PREFIX": ""}
    )
    client = myapp.test_client()
    login(client, "secret")

    # Specter
    result = client.get("/")
    assert result.status_code == 404  # / --> 404
    result = client.get("/someprefix/")
    assert result.status_code == 302  # REDIRECT.
    result = client.get("/someprefix/welcome")
    assert result.status_code == 308  # REDIRECT.
    result = client.get("/someprefix/welcome/")
    assert result.status_code == 302  # REDIRECT.
    result = client.get("/someprefix/welcome/about")
    assert b"Welcome to Specter" in result.data

    # Extensions
    result = client.get("/someprefix/spc/ext/swan/")
    # The swan extension will automatically redirect to /settings/auth
    assert result.status_code == 302
    assert result.location.endswith("/someprefix/settings/auth")


def test_SPECTER_URL_PREFIX(caplog):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    myapp = specter_app_with_config(
        config={
            "APP_URL_PREFIX": "",
            "SPECTER_URL_PREFIX": "/someprefix",
            "EXT_URL_PREFIX": "/someprefix/extensions",
        }
    )
    client = myapp.test_client()
    login(client, "secret")
    result = client.get("/")
    # The effect is almost the same but you get one more convenient redirect
    assert result.status_code == 302  # REDIRECT.
    result = client.get("/someprefix/")
    assert result.status_code == 302  # REDIRECT.
    result = client.get("/someprefix/welcome")
    assert result.status_code == 308  # REDIRECT.
    result = client.get("/someprefix/welcome/")
    assert result.status_code == 302  # REDIRECT.
    result = client.get("/someprefix/welcome/about")
    assert b"Welcome to Specter" in result.data

    # Extensions
    result = client.get("/someprefix/extensions/swan/")
    # The swan extension will automatically redirect to /settings/auth
    assert result.status_code == 302
    assert result.location.endswith("/someprefix/settings/auth")


def specter_app_w2ith_config(config={}):
    """the Flask-App, but uninitialized"""
    # class tempClass(TestConfig):
    #    ''' For now, this can only be used once as a config object :-| '''
    #    pass
    tempClass = type("tempClass", (TestConfig,), {})
    for key, value in config.items():
        setattr(tempClass, key, value)
    # service_manager will expect the class to be defined as a direct property of the module:
    if hasattr(sys.modules[__name__], "tempClass"):
        delattr(sys.modules[__name__], "tempClass")
    assert not hasattr(sys.modules[__name__], "tempClass")
    setattr(sys.modules[__name__], "tempClass", tempClass)
    assert hasattr(sys.modules[__name__], "tempClass")
    assert getattr(sys.modules[__name__], "tempClass") == tempClass
    app = create_app(config=tempClass)
    assert (
        app.config["SPECTER_CONFIGURATION_CLASS_FULLNAME"]
        == "test_ep_controller.tempClass"
    )
    for key, value in config.items():
        assert app.config[key] == value

    app.app_context().push()
    app.config["TESTING"] = True
    app.testing = True
    app.tor_service_id = None
    app.tor_enabled = False
    init_app(app, specter=Specter())
    test123: Blueprint = app.blueprints["swan_endpoint"]
    for vf in app.view_functions:
        print(vf)
    # assert app.view_functions == " "
    return app


def login(client, password):
    """login helper-function"""
    result = client.post(
        "auth/login", data=dict(password=password), follow_redirects=True
    )
    assert (
        b"We could not check your password, maybe Bitcoin Core is not running or not configured?"
        not in result.data
    )
    return result


def logout(client):
    """logout helper-method"""
    return client.get("auth/logout", follow_redirects=True)
