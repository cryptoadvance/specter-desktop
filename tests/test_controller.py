import logging
import pytest


def test_home(caplog, client):
    """ The root of the app """
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    login(client, "secret")
    result = client.get("/")
    # By default there is no authentication
    assert result.status_code == 302  # REDIRECT.
    result = client.get("/about")
    assert b"Welcome to Specter" in result.data
    result = client.get("/devices/new_device", follow_redirects=True)
    assert result.status_code == 200  # OK.
    assert b"Add Device" in result.data
    result = client.get("/settings", follow_redirects=True)
    assert result.status_code == 200  # OK.
    assert b"settings - Specter Desktop" in result.data
    result = client.get("/wallets/new_wallet", follow_redirects=True)
    assert result.status_code == 200  # OK.
    assert b"Select the type of the wallet" in result.data

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


def test_settings_general(caplog, client):
    login(client, "secret")
    result = client.get("/settings/general", follow_redirects=True)
    assert b"Network:" in result.data
    assert b"regtest" in result.data


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
            explorer="",
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
    assert b"Specter data was successfully loaded from backup." in result.data
    assert b"SimpleMyNiceDevice" in result.data
    # assert b'btc Hot Wallet' in result.data # Not sure why this doesn't work
    assert b"myNiceDevice" in result.data
    assert b"btchot" in result.data


def login(client, password):
    """ login helper-function """
    result = client.post(
        "auth/login", data=dict(password=password), follow_redirects=True
    )
    assert (
        b"We could not check your password, maybe Bitcoin Core is not running or not configured?"
        not in result.data
    )
    return result


def logout(client):
    """ logout helper-method """
    return client.get("auth/logout", follow_redirects=True)
