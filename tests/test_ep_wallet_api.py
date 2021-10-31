import logging
import pytest


def test_fees(caplog, client):
    """The root of the app"""
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    login(client, "secret")
    result = client.get("/wallets/fees")
    assert result.status_code == 200
    assert (
        result.data
        == b'{"fastestFee": 6, "halfHourFee": 1, "hourFee": 1, "minimumFee": 1}'
    )
    logout(client)


# Ugly: Code duplication. Cannot import from other test_modules
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
