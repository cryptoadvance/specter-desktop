from datetime import datetime
import json
import logging
from unittest.mock import MagicMock, patch
import mock

import pytest
from werkzeug.wrappers import Response

from cryptoadvance.specter.wallet import Wallet


def test_fees(caplog, client):
    """The root of the app"""
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    login(client, "secret")
    result = client.get("/wallets/fees")
    assert result.status_code == 200
    my_dict = json.loads(result.data)
    assert my_dict["result"]["fastestFee"] == 1
    assert my_dict["error_messages"] == []
    logout(client)


@patch("cryptoadvance.specter.server_endpoints.wallets_api.get_price_at")
@patch("cryptoadvance.specter.server_endpoints.wallets_api._")
def test_txlist_to_csv(
    mock_babel: MagicMock,
    mock_get_price_at: MagicMock,
    caplog,
    app,
    specter_regtest_configured,
    funded_hot_wallet_1,
):
    caplog.set_level(logging.DEBUG)

    def fake_translate(text):
        return text

    mock_babel.side_effect = fake_translate
    mock_get_price_at.return_value = 1000000, "$"
    assert mock_get_price_at() == (1000000, "$")

    with app.test_request_context():
        from cryptoadvance.specter.server_endpoints.wallets_api import txlist_to_csv

        curr_date = datetime.now()
        for i, tx in enumerate(
            txlist_to_csv(
                funded_hot_wallet_1,
                funded_hot_wallet_1.txlist(),
                includePricesHistory=True,
            )
        ):

            tx = tx.split(",")
            print(f"{i} {tx}")
            if i == 0:
                assert tx[0] == "Date"
                assert tx[1] == "Label"
                assert tx[2] == "Category"
                assert tx[3] == "Amount (BTC)"
                assert tx[4] == "Value (USD)"
                assert tx[5] == "Rate (BTC/USD)"
                assert tx[6] == "TxID"
                assert tx[7] == "Address"
                assert tx[8] == "Block Height"
                assert tx[9].strip() == "Timestamp"
                continue
            assert tx[0] == curr_date.strftime("%Y-%m-%d")
            assert tx[1].startswith("Address #")
            assert tx[2] == "receive"
            assert float(tx[3]) > 0
            assert (
                float(tx[4]) <= 1000000 * 10
            )  # funded_hot_wallet_1 has no transactions >= 10 btc
            assert float(tx[5]) == 1000000
            assert tx[7].startswith("bcrt1")
            # stupid, why not simply 0:
            if isinstance(tx[8], str) and tx[8] == "Unconfirmed":
                pass
            else:
                assert int(tx[8]) > 0
            assert (
                datetime.strptime(tx[9].strip(), "%Y-%m-%d %H:%M:%S") - curr_date
            ).total_seconds() < 120  # less than 2 minutes difference (for super slow pytesting)
    # assert False


@patch("cryptoadvance.specter.server_endpoints.wallets_api.get_price_at")
@patch("cryptoadvance.specter.server_endpoints.wallets_api._")
def test_addresses_list_to_csv(
    mock_babel: MagicMock,
    mock_get_price_at: MagicMock,
    caplog,
    app,
    specter_regtest_configured,
    funded_hot_wallet_1: Wallet,
):
    """addresses_list_to_csv does not seem to be used, though"""
    caplog.set_level(logging.INFO)

    def fake_translate(text):
        return text

    mock_babel.side_effect = fake_translate
    mock_get_price_at.return_value = 1000000, "$"
    assert mock_get_price_at() == (1000000, "$")

    with app.test_request_context():
        from cryptoadvance.specter.server_endpoints.wallets_api import (
            addresses_list_to_csv,
        )

        # update balancess
        funded_hot_wallet_1.update()

        curr_date = datetime.now()
        for i, addr in enumerate(addresses_list_to_csv(funded_hot_wallet_1)):

            addr = addr.split(",")
            print(f"{i} {addr}")
            if i == 0:
                assert addr[0] == "Address"
                assert addr[1] == "Label"
                assert addr[2] == "Index"
                assert addr[3] == "Used"
                assert addr[4].strip() == "Current balance"
                continue
            assert addr[0].startswith("bcrt1")
            assert addr[1].startswith("Address #")
            # assert int(addr[2]) == i
            assert bool(addr[3])
            assert float(addr[4].strip()) > 0


def test_txout_set_info(caplog, app, client):
    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    login(client, "secret")
    res = client.get("/wallets/get_txout_set_info")
    assert res.status == "200 OK"
    print(json.loads(res.data))
    assert json.loads(res.data)["total_amount"] > 0


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
