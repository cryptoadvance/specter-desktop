import pytest
import mock
from mock import Mock
from cryptoadvance.specter.services.swan.client import SwanApiException, SwanClient


def test_SwanClient(app):
    sc = SwanClient("a_hostname", "a_access_token", 123123, "a_refresh_token")
    with app.app_context():
        assert not sc.is_access_token_valid()
        assert (
            sc.calc_callback_url() == "http://a_hostname/spc/ext/swan/oauth2/callback"
        )

        start_url = sc.get_oauth2_start_url("a_hostname")
        start_url.startswith(
            "https://dev-api.swanbitcoin.com/oidc/auth?client_id=specter-dev&redirect_uri=http://a_hostname/spc/ext/swan/oauth2/callback&response_type=code&response_mode=query"
        )

        fake_response = Mock()
        fake_response.text = """
            {
                "access_token": "muuuhTheAccessToken",
                "expires_in": 3600,
                "refresh_token": "***************",
                "scope": "offline_access v1 write:vendor_wallet read:vendor_wallet write:automatic_withdrawal read:automatic_withdrawal",
                "token_type": "Bearer"
            }
        """
        with mock.patch("requests.post", return_value=fake_response):
            assert sc._get_access_token() == "muuuhTheAccessToken"
        assert sc.access_token_expires != 123123
        assert sc.is_access_token_valid()

        fake_response.status_code = 200
        fake_response.json.return_value = {"some": "json"}
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

        # Issues with Babel with this test
        # with mock.patch('requests.request', return_value=fake_response):
        #    assert sc.update_autowithdrawal_addresses("someWalletId", "walletName", "walletAlias", [1,2,3]) == "someWalletId"
