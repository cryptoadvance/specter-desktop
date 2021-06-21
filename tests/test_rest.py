import json
import base64
import logging


def test_rr_psbt_get(client, caplog):
    caplog.set_level(logging.DEBUG)
    """ testing the registration """
    # Unauthorized
    result = client.get("/api/v1alpha/wallets/some_wallet/psbt", follow_redirects=True)
    assert result.status_code == 401
    assert json.loads(result.data)["message"].startswith(
        "The server could not verify that you are authorized to access the URL requested."
    )

    # Wrong password
    headers = {
        "Authorization": "Basic "
        + base64.b64encode(bytes("admin" + ":" + "wrongPassword", "ascii")).decode(
            "ascii"
        )
    }
    result = client.get(
        "/api/v1alpha/wallets/simple/psbt", follow_redirects=True, headers=headers
    )
    assert result.status_code == 401
    assert json.loads(result.data)["message"].startswith(
        "The server could not verify that you are authorized to access the URL requested."
    )

    # Proper authenticated but not authorized
    headers = {
        "Authorization": "Basic "
        + base64.b64encode(bytes("someuser" + ":" + "somepassword", "ascii")).decode(
            "ascii"
        )
    }
    result = client.get(
        "/api/v1alpha/wallets/simple/psbt", follow_redirects=True, headers=headers
    )
    assert result.status_code == 403
    assert json.loads(result.data)["message"].startswith(
        "You don't have the permission to access the requested resource."
    )

    # Proper authorized
    headers = {
        "Authorization": "Basic "
        + base64.b64encode(bytes("admin" + ":" + "admin", "ascii")).decode("ascii")
    }
    result = client.get(
        "/api/v1alpha/wallets/simple/psbt", follow_redirects=True, headers=headers
    )
    assert result.status_code == 200
    assert result.data == b"[]\n"


def test_rr_psbt_post(client, caplog):
    caplog.set_level(logging.DEBUG)
    """ testing the registration """
    result = client.post(
        "/api/v1alpha/wallets/some_wallet/psbt",
        data=dict(address="someaddress", amount=0.5),
        follow_redirects=True,
    )
    assert result.status_code == 401
    assert json.loads(result.data)["message"].startswith(
        "The server could not verify that you are authorized to access the URL requested."
    )

    headers = {
        "Authorization": "Basic "
        + base64.b64encode(bytes("admin" + ":" + "admin", "ascii")).decode("ascii")
    }
    result = client.post(
        "/api/v1alpha/wallets/some_wallet/psbt",
        data=dict(address="someaddress", amount=0.5),
        follow_redirects=True,
        headers=headers,
    )
    assert result.status_code == 200
    assert result.data == ""
