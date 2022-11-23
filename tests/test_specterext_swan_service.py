from mock import patch
from cryptoadvance.specterext.swan.service import SwanService
import json


class SwanServiceNoEncryption(SwanService):
    id = "reckless_swan"
    encrypt_data = False


@patch(
    "cryptoadvance.specterext.swan.client.SwanClient.update_autowithdrawal_addresses"
)
def test_reserve_addresses(mocked_update_autowithdrawal_addresses, app_no_node, wallet):
    mocked_update_autowithdrawal_addresses.return_value = "some_id"
    specter = app_no_node.specter
    storage_manager = specter.service_unencrypted_storage_manager
    swan = SwanServiceNoEncryption(True, specter)
    # No data stored befre the reserve_addresses call
    assert storage_manager.get_current_user_service_data("reckless_swan") == {}
    # We need to mock flask's request context since reserve_addresses is calling client() which in turn calls request.url
    # Since we already have a test app, the easiest way is to use app.test_request_context(). For details see:
    # https://stackoverflow.com/questions/36729846/mock-flask-request-in-python-nosetests
    with app_no_node.test_request_context():
        swan.reserve_addresses(wallet, label="Swan withdrawals", num_addresses=5)
        # Check that the correct addresse list was passed to the client's update_autowithdrawal_addresses-method, should be addresses #1, #3, #5, #7, #9 from the test_wallet (the first address is skipped)
        addresses = [
            "bcrt1qsqnuk9hulcfta7kj7687favjv66d5e9yy0lr7t",
            "bcrt1qee494mauu3fv5aje0t4p6e52hvwq6d5hcqfxqt",
            "bcrt1qpnem6p9vr8rmjsf7k49p9sleu0h020g34ggn6k",
            "bcrt1q8534jsqkympwaelaqxhvfr6hc3g8y4kjtgr6d6",
            "bcrt1qxd6ndd7mt7jqut7797l84675fz4kqhs4fcfgny",
        ]
        assert (
            mocked_update_autowithdrawal_addresses.call_args_list[0].kwargs["addresses"]
            == addresses
        )
        # Also check that the wallet reserved the correct addresses
        address_obj_list = wallet.get_associated_addresses("reckless_swan")
        assert [address["address"] for address in address_obj_list] == addresses
        # Check that the reserve_addresses was successful, we should have a swan_wallet_id now and the name of the associated (Specter) wallet
        assert storage_manager.get_current_user_service_data("reckless_swan") == {
            "swan_wallet_id": "some_id",
            "wallet": wallet.alias,
        }
        mocked_update_autowithdrawal_addresses.return_value = "new_id"
        # We are getting a new id since we request to reserve more addresses as we've already reserved
        swan.reserve_addresses(wallet, label="Swan withdrawals", num_addresses=7)
        # Adding address #11 and #13
        additional_addresses = [
            "bcrt1q32gd5s7rk9ptkv8e74q4c64ntf48u4sza6c9d9",
            "bcrt1q463mg67f3tj5d223vf6387ty30qlx2wep4s5gp",
        ]
        addresses.extend(additional_addresses)
        assert (
            mocked_update_autowithdrawal_addresses.call_args_list[1].kwargs["addresses"]
            == addresses
        )
        assert storage_manager.get_current_user_service_data("reckless_swan") == {
            "swan_wallet_id": "new_id",
            "wallet": wallet.alias,
        }
        mocked_update_autowithdrawal_addresses.return_value = "another_new_id"
        # We are not getting a new id since we've already reserved 7 addresses
        swan.reserve_addresses(wallet, label="Swan withdrawals", num_addresses=7)
        # Check that update_autowithdrawal_addresses was not called anymore (we had two calls so far)
        assert len(mocked_update_autowithdrawal_addresses.mock_calls) == 2
        assert storage_manager.get_current_user_service_data("reckless_swan") == {
            "swan_wallet_id": "new_id",
            "wallet": wallet.alias,
        }


class SwanServiceWithMockedMethods(SwanService):
    id = "mocked_swan"
    encrypt_data = False
    # Basically patching the reserve_addresses function like this, to avoid making the SwanService to a complete mock
    @classmethod
    def reserve_addresses(cls, wallet, label: str = None, num_addresses: int = 10):
        pass


@patch("cryptoadvance.specterext.swan.client.SwanClient.set_autowithdrawal")
def test_set_autowithdrawal_settings(mocked_set_autowithdrawal, app_no_node, wallet):
    autowithdrawal_api_response = """
            {
                "entity": "automaticWithdrawal",
                "item": {
                    "id": "some_important_withdrawal_id",
                    "minBtcThreshold": "0.05",
                    "isActive": false,
                    "isCanceled": false,
                    "createdAt": "2022-01-07T02:14:56.070Z",
                    "walletId": "******************",
                    "walletAddressId": null
                }
            }
        """
    mocked_set_autowithdrawal.return_value = json.loads(autowithdrawal_api_response)
    specter = app_no_node.specter
    storage_manager = specter.service_unencrypted_storage_manager
    swan = SwanServiceWithMockedMethods(True, specter)
    with app_no_node.test_request_context():
        swan.set_autowithdrawal_settings(wallet, 0.05)
        assert storage_manager.get_current_user_service_data("mocked_swan") == {
            "autowithdrawal_id": "some_important_withdrawal_id",
            "withdrawal_threshold": 0.05,
        }
