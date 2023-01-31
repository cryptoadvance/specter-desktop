from mock import patch
from cryptoadvance.specterext.swan.service import SwanService
from cryptoadvance.specter.wallet import Wallet
import json


class SwanServiceNoEncryption(SwanService):
    id = "reckless_swan"
    encrypt_data = False


@patch(
    "cryptoadvance.specterext.swan.client.SwanClient.update_autowithdrawal_addresses"
)
def test_reserve_addresses(
    mocked_update_autowithdrawal_addresses, app_no_node, trezor_wallet_acc5: Wallet
):
    wallet = trezor_wallet_acc5
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
            "bcrt1qrfdnsdhmp5chxxexywdz37ppre7s5f0y4z4ykn",
            "bcrt1qp8hq4ngf0uy4r5atackw9ak5ngl8vfd54dz226",
            "bcrt1qsdzhz4q8y32maeay899jyfdw03pdlrrktx838g",
            "bcrt1qc65gchplxw57e7hdzdxcudjq90y0y3mxm9m96l",
            "bcrt1qasuqqj5u7t5e8zr3ug68yzfr2fjj4eg4u4ucj4",
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
            "bcrt1qa4n6687f53recfcthfu2xpgcwcqvmzz4pdfw98",
            "bcrt1qcxq5md4jsnldpc6fswld8edaxgzpstamswt3r6",
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
def test_set_autowithdrawal_settings(
    mocked_set_autowithdrawal, app_no_node, trezor_wallet_acc3
):
    wallet = trezor_wallet_acc3
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
