from ast import Call
from datetime import datetime
import json
import logging
from unittest.mock import MagicMock
import pytest
import mock
from mock import Mock, patch
from cryptoadvance.specterext.swan.client import (
    SwanApiRefreshTokenException,
    SwanClient,
)

logger = logging.getLogger(__name__)


def construct_access_token_fake_response():
    fake_response_text = """
    {
        "access_token": "muuuhTheAccessToken",
        "expires_in": 3600,
        "refresh_token": "***************",
        "scope": "offline_access v1 write:vendor_wallet read:vendor_wallet write:automatic_withdrawal read:automatic_withdrawal",
        "token_type": "Bearer"
    }
"""
    fake_response = Mock()
    fake_response.text = fake_response_text
    fake_response.status_code = 200
    fake_response.json.return_value = json.loads(fake_response_text)
    return fake_response


def construct_addresses_fake_response():
    fake_response_text = """
            {
                "entity": "wallet",
                "item": {
                    "id": "someOtherWalletId",
                    "isConfirmed": false,
                    "displayName": "Specter autowithdrawal to SeedSigner demo",
                    "metadata": {
                        "oidc": {
                            "clientId": "specter-dev"
                        },
                        "specter_wallet_alias": "seedsigner_demo"
                    }
                }
            }
    """
    fake_response = Mock()
    fake_response.text = fake_response_text
    fake_response.status_code = 200
    fake_response.json.return_value = json.loads(fake_response_text)
    return fake_response


def test_SwanClient(app):
    sc = SwanClient("a_hostname", "a_access_token", 123123, "a_refresh_token")
    with app.app_context():
        assert not sc.is_access_token_valid()
        assert sc.calc_callback_url() == "http://a_hostname/svc/swan/oauth2/callback"

        start_url = sc.get_oauth2_start_url("a_hostname")
        start_url.startswith(
            "https://dev-api.swanbitcoin.com/oidc/auth?client_id=specter-dev&redirect_uri=http://a_hostname/spc/ext/swan/oauth2/callback&response_type=code&response_mode=query"
        )

        fake_response = construct_access_token_fake_response()
        with mock.patch("requests.post", return_value=fake_response):
            assert sc._get_access_token() == "muuuhTheAccessToken"
        assert sc.access_token_expires != 123123
        assert sc.is_access_token_valid()
        with mock.patch("requests.get", return_value=fake_response):
            assert (
                sc.authenticated_request(
                    "/some/endpoint", json_payload={"muuh": "meeh"}
                )
                == fake_response.json.return_value
            )
            assert (
                sc.get_autowithdrawal_addresses("someWalletId")
                == fake_response.json.return_value
            )


def test_still_valid_access_token(app):
    sc = SwanClient(
        "a_hostname", "forever_valid_access_token", 5000000000, "a_refresh_token"
    )
    with app.app_context():
        fake_response = construct_access_token_fake_response()
        with mock.patch("requests.post", return_value=fake_response):
            assert sc.is_access_token_valid() == True
            assert sc._get_access_token() != "muuuhTheAccessToken"
            assert sc._get_access_token() == "forever_valid_access_token"


def test_expired_access_token():
    sc = SwanClient("umbrel", "aging_access_token", 1000, "")
    assert sc.is_access_token_valid() == False
    with pytest.raises(
        SwanApiRefreshTokenException,
        match="access_token is expired but we don't have a refresh_token",
    ):
        sc._get_access_token()


@patch("requests.delete")
@patch("requests.request")
@patch("requests.patch")
@patch("cryptoadvance.specterext.swan.client._")
def test_SwanClient_update_autowithdrawal_addresses(
    mock_babel: MagicMock,
    mock_req_post: MagicMock,
    mock_req_request: MagicMock,
    mock_req_delete: MagicMock,
    caplog,
    app,
):
    caplog.set_level(logging.DEBUG)

    def fake_translate(text):
        return text

    mock_babel.side_effect = fake_translate
    fake_response = construct_addresses_fake_response()
    mock_req_request.return_value = fake_response
    mock_req_post.return_value = fake_response

    curr_timstamp = (
        int(round(datetime.now().timestamp())) + 300
    )  # should not expire in the next 300 seconds
    sc = SwanClient("a_hostname", "a_access_token", curr_timstamp, "a_refresh_token")

    with app.app_context():
        address_list = [
            "bcrt1q4zcc0yppghquz9tzsd9k34m8rpmvav953hx3mk",
            "bcrt1q2lmvfypnqcr7w9vcrlem7vdn7w65ac90x2ef6x",
            "bcrt1quazsqywlme8ps70vq7xckflztghypp0r4ck9yw",
        ]
        assert (
            sc.update_autowithdrawal_addresses(
                "someWalletId", "walletName", "walletAlias", address_list
            )
            == "someOtherWalletId"
        )

        # Check that the addresse send to the Swan API are in the correct format
        patch_call: Call = mock_req_request.call_args_list[1]
        json_payload = patch_call.kwargs["json"]
        # "btcAddresses" should look like this:
        """ {'btcAddresses': [{'address': 'bcrt1q4zcc0yppghquz9tzsd9k34m8rpmvav953hx3mk'}, 
        {'address': 'bcrt1q2lmvfypnqcr7w9vcrlem7vdn7w65ac90x2ef6x'}, 
        {'address': 'bcrt1quazsqywlme8ps70vq7xckflztghypp0r4ck9yw'}] """
        assert isinstance(json_payload["btcAddresses"], list)
        for address in json_payload["btcAddresses"]:
            assert isinstance(address, dict)
            assert isinstance(
                address["address"], str
            ), "Swan is expecting an almost flat list of addresses"
