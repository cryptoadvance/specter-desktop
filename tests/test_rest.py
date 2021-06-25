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

    # Admin but not authorized (admin is NOT allowed to read everything)
    headers = {
        "Authorization": "Basic "
        + base64.b64encode(bytes("admin" + ":" + "admin", "ascii")).decode("ascii")
    }
    result = client.get(
        "/api/v1alpha/wallets/simple/psbt", follow_redirects=True, headers=headers
    )
    assert result.status_code == 403
    print(result.data)
    assert json.loads(result.data)["message"].startswith("Wallet simple does not exist")

    # Proper authorized (the wallet is owned by someuser)
    headers = {
        "Authorization": "Basic "
        + base64.b64encode(bytes("someuser" + ":" + "somepassword", "ascii")).decode(
            "ascii"
        )
    }
    result = client.get(
        "/api/v1alpha/wallets/a_simple_wallet/psbt",
        follow_redirects=True,
        headers=headers,
    )
    assert result.status_code == 200
    data = json.loads(result.data)
    assert data["result"] == []


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
        + base64.b64encode(bytes("someuser" + ":" + "somepassword", "ascii")).decode(
            "ascii"
        ),
        "Content-type": "application/json",
    }
    result = client.post(
        "/api/v1alpha/wallets/a_simple_wallet/psbt",
        data="""
        {
            "recipients" : [
                { 
                    "address": "BCRT1qgc6h85z43g3ss2dl5zdrzrp3ef6av4neqcqhh8",
                    "amount": 0.1,
                    "unit": "btc",
                    "label": "someLabel"
                },
                {
                    "address": "bcrt1q3kfetuxpxvujasww6xas94nawklvpz0e52uw8a",
                    "amount": 111211,
                    "unit": "sat",
                    "label": "someOtherLabel"
                }
            ],
            "rbf_tx_id": "",
            "subtract_from": "1",
            "fee_rate": "64",
            "rbf": true
        }
        """,
        follow_redirects=True,
        headers=headers,
    )
    print(result.data)
    assert result.status_code == 200
    data = json.loads(result.data)
    assert "bcrt1qgc6h85z43g3ss2dl5zdrzrp3ef6av4neqcqhh8" in data["result"]["address"]
    assert "bcrt1q3kfetuxpxvujasww6xas94nawklvpz0e52uw8a" in data["result"]["address"]
    assert 0.1 in data["result"]["amount"]
    assert 0.00111211 in data["result"]["amount"]
    assert data["result"]["tx"]
    assert data["result"]["inputs"]
    assert data["result"]["outputs"]
    assert data["result"]["fee_rate"] == "0.00064000"
    assert data["result"]["tx_full_size"]
    assert data["result"]["base64"]
    assert data["result"]["time"]
    assert data["result"]["sigs_count"] == 0
