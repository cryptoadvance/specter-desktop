import base64
import json
import logging
from numbers import Number
import jwt
import pytest
import datetime
import random

from flask import current_app as app
from cryptoadvance.specter.managers.device_manager import DeviceManager
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.util.wallet_importer import WalletImporter
from cryptoadvance.specter.user import User

logger = logging.getLogger(__name__)


def almost_equal(a: Number, b: Number, precision: float = 0.01) -> bool:
    """
    Checks if a and b are not very different.
    Default precision is 1%
    """
    if a == b:
        return True
    diff = 2 * (a - b) / (a + b)
    return (diff < precision) and (diff > -precision)


def test_rr_psbt_get(client, specter_regtest_configured, bitcoin_regtest, caplog):
    create_a_simple_wallet(specter_regtest_configured, bitcoin_regtest)
    assert (
        specter_regtest_configured.config["testing"]["allow_threading_for_testing"]
        == False
    )  # Tests fail with threading
    caplog.set_level(logging.DEBUG)
    """ testing the registration """
    # Unauthorized
    result = client.get("/api/v1alpha/wallets/some_wallet/psbt", follow_redirects=True)
    assert result.status_code == 401
    assert json.loads(result.data)["message"].startswith(
        "The server could not verify that you are authorized to access the URL requested."
    )

    # Wrong token
    headers = {"Authorization": "Bearer " + "sometoken"}
    result = client.get(
        "/api/v1alpha/wallets/a_simple_wallet/psbt",
        follow_redirects=True,
        headers=headers,
    )
    assert result.status_code == 401
    assert json.loads(result.data)["message"].startswith(
        "The server could not verify that you are authorized to access the URL requested."
    )

    # Admin but not authorized (admin is NOT allowed to read everything)
    headers = {
        "Authorization": "Bearer "
        + User.generate_jwt_token(
            "admin", "tokenid", "tokendescription", random.randrange(100, 200)
        )
    }
    result = client.get(
        "/api/v1alpha/wallets/a_simple_wallet/psbt",
        follow_redirects=True,
        headers=headers,
    )
    assert result.status_code == 403
    assert (
        json.loads(result.data)["message"]
        == "The wallet does not belong to the user in the request."
    )

    # Proper authorized (the wallet is owned by someuser)
    headers = {
        "Authorization": "Bearer "
        + User.generate_jwt_token(
            "someuser", "tokenid", "tokendescription", random.randrange(100, 200)
        )
    }
    result = client.get(
        "/api/v1alpha/wallets/a_simple_wallet/psbt",
        follow_redirects=True,
        headers=headers,
    )
    assert result.status_code == 200
    data = json.loads(result.data)
    assert data["result"] == {}


def test_rr_psbt_post(specter_regtest_configured, bitcoin_regtest, client, caplog):
    create_a_simple_wallet(specter_regtest_configured, bitcoin_regtest)
    caplog.set_level(logging.DEBUG)
    """ testing the registration """

    headers = {
        "Authorization": "Bearer "
        + User.generate_jwt_token(
            "someuser", "tokenid", "tokendescription", random.randrange(100, 200)
        ),
        "Content-type": "application/json",
    }

    result = client.get(
        "/api/v1alpha/wallets/a_simple_wallet/",
        follow_redirects=True,
        headers=headers,
    )
    # Why the heck does this fail?
    # assert json.loads(result.data)["a_simple_wallet"]["info"]["balance"] > 0

    result = client.post(
        "/api/v1alpha/wallets/some_wallet/psbt",
        data=dict(address="someaddress", amount=0.5),
        follow_redirects=True,
    )
    assert result.status_code == 401
    assert json.loads(result.data)["message"].startswith(
        "The server could not verify that you are authorized to access the URL requested."
    )

    result = client.post(
        "/api/v1alpha/wallets/a_simple_wallet/psbt",
        data="""
        {
            "recipients" : [
                { 
                    "address": "bcrt1qgc6h85z43g3ss2dl5zdrzrp3ef6av4neqcqhh8",
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
            "subtract_from": "0",
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
    assert almost_equal(data["result"]["fee_rate"], 64)
    assert data["result"]["tx_full_size"]
    assert data["result"]["base64"]
    assert data["result"]["time"]
    assert data["result"]["sigs_count"] == 0


def create_a_simple_wallet(specter: Specter, bitcoin_regtest):
    """ToDo: Could potentially do this with a fixture but this is only relevant for this file only"""
    payload = jwt.decode(
        User.generate_jwt_token(
            "someuser", "tokenid", "tokendescription", random.randrange(100, 200)
        ),
        app.config["SECRET_KEY"],
        algorithms=["HS256"],
    )
    username = payload["username"]
    someuser = specter.user_manager.get_user_by_username(username)
    wm = someuser.wallet_manager
    assert not wm.working_folder is None
    # Create a Wallet
    wallet_json = '{"label": "a_simple_wallet", "blockheight": 0, "descriptor": "wpkh([1ef4e492/84h/1h/0h]tpubDC5EUwdy9WWpzqMWKNhVmXdMgMbi4ywxkdysRdNr1MdM4SCfVLbNtsFvzY6WKSuzsaVAitj6FmP6TugPuNT6yKZDLsHrSwMd816TnqX7kuc/0/*)#xp8lv5nr", "devices": [{"type": "trezor", "label": "trezor"}]} '
    dm = someuser.device_manager
    wallet_importer = WalletImporter(wallet_json, specter, device_manager=dm)
    wallet_importer.create_nonexisting_signers(
        dm,
        {"unknown_cosigner_0_name": "trezor", "unknown_cosigner_0_type": "trezor"},
    )
    wallet = wallet_importer.create_wallet(wm)
    try:
        # fund it with some coins
        bitcoin_regtest.testcoin_faucet(address=wallet.getnewaddress())
        # make sure it's confirmed
        bitcoin_regtest.mine()
        # Realize that the wallet has funds:
        wallet.update()
    except SpecterError as se:
        if str(se).startswith("Timeout"):
            pytest.fail(
                "We got a Bitcoin-RPC timeout while setting up the test, minting some coins. Test Error! Check cpu/mem utilastion and btc/elem logs!"
            )
            return
        else:
            raise se

    assert wallet.fullbalance >= 20
