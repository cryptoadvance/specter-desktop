from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.managers.user_manager import UserManager
from cryptoadvance.specter.wallet import Wallet
import logging

logger = logging.getLogger(__name__)
from cryptoadvance.specter.global_search import GlobalSearchTree
from unittest.mock import MagicMock, patch
from fix_devices_and_wallets import create_hot_wallet_device, create_hot_wallet_with_ID


def mock_url_for(url, **kwargs):
    return f"{url}/".replace(".", "/") + "/".join(kwargs.values())


@patch("cryptoadvance.specter.global_search.url_for", mock_url_for)
@patch("cryptoadvance.specter.global_search._", str)
def test_transactions(specter_regtest_configured: Specter, funded_hot_wallet_1):
    user = specter_regtest_configured.user_manager.user
    global_search_tree = GlobalSearchTree()

    # test wallet name
    search_term = funded_hot_wallet_1.alias.upper()[3:8]
    results = global_search_tree.do_global_search(
        search_term,
        user,
        specter_regtest_configured.hide_sensitive_info,
        specter_regtest_configured.wallet_manager.wallets,
        specter_regtest_configured.device_manager.devices,
    )
    assert len(results["result_dicts"]) == 1
    assert len(results["result_dicts"][0]["search_results"]) == 2
    assert results["result_dicts"][0]["search_results"][0]["key"] == "Alias"
    assert (
        results["result_dicts"][0]["search_results"][0]["value"]
        == funded_hot_wallet_1.alias
    )
    assert results["result_dicts"][0]["search_results"][1]["key"] == "Name"
    assert (
        results["result_dicts"][0]["search_results"][1]["value"]
        == funded_hot_wallet_1.name
    )

    unspent_list = funded_hot_wallet_1.rpc.listunspent()
    assert unspent_list  # otherwise the test will not test anything
    # logger.info(unspent_list)

    # test ALL utxos, to ensure that the search really can find ALL information
    logger.info(f"Searching for  {len(unspent_list)} unspent transactions and utxo")
    for tx in unspent_list:
        # test txids
        search_term = tx["txid"].upper()  # checks the case insensitive search
        results = global_search_tree.do_global_search(
            search_term,
            user,
            specter_regtest_configured.hide_sensitive_info,
            specter_regtest_configured.wallet_manager.wallets,
            specter_regtest_configured.device_manager.devices,
        )

        # logger.info(results)
        assert results["search_term"] == search_term
        assert (
            len(results["result_dicts"]) == 2
        )  # 1 result in utxo and 1 result in tx history

        sorted_result_dicts = sorted(
            results["result_dicts"],
            key=lambda result_dict: result_dict["search_results"][0]["click_action"][
                "url"
            ],
        )

        expectations = [
            {
                "value": tx["txid"],
                "title": tx["txid"],
                "key": "Txid",
                "click_action": {
                    "url": f"wallets_endpoint/history_tx_list_type/{funded_hot_wallet_1.alias}/txlist",
                    "method_str": "form",
                    "form_data": {"action": "show_tx_on_load", "txid": tx["txid"]},
                },
            },
            {
                "value": tx["txid"],
                "title": tx["txid"],
                "key": "Txid",
                "click_action": {
                    "url": f"wallets_endpoint/history_tx_list_type/{funded_hot_wallet_1.alias}/utxo",
                    "method_str": "form",
                    "form_data": {"action": "show_tx_on_load", "txid": tx["txid"]},
                },
            },
        ]
        for result_dict, expectation in zip(sorted_result_dicts, expectations):
            assert len(result_dict["search_results"]) == 1
            assert result_dict["search_results"][0] == expectation

    # test amount search of the 1. utxo
    search_amount = "1.0"
    # count how many of the other utxos also have this amount
    number_of_utxos_with_this_amount = len(
        [
            utxo
            for utxo in unspent_list
            if search_amount.lower() in str(utxo["amount"]).lower()
        ]
    )
    assert number_of_utxos_with_this_amount > 0
    results = global_search_tree.do_global_search(
        str(search_amount),
        user,
        specter_regtest_configured.hide_sensitive_info,
        specter_regtest_configured.wallet_manager.wallets,
        specter_regtest_configured.device_manager.devices,
    )

    sorted_result_dicts = sorted(
        results["result_dicts"],
        key=lambda result_dict: result_dict["search_results"][0]["click_action"]["url"],
    )
    tx_result = sorted_result_dicts[0]
    len(tx_result["search_results"]) == number_of_utxos_with_this_amount


@patch("cryptoadvance.specter.global_search.url_for", mock_url_for)
@patch("cryptoadvance.specter.global_search._", str)
def test_addresses(specter_regtest_configured: Specter, unfunded_hot_wallet_1):
    user = specter_regtest_configured.user_manager.user
    global_search_tree = GlobalSearchTree()

    # change addresses
    addresses = unfunded_hot_wallet_1.addresses_info(is_change=True)
    logger.info(f"Searching for  {len(addresses)} change addresses")
    assert addresses
    for i, address in enumerate(addresses):
        search_term = address["address"].upper()  # checks the case insensitive search
        results = global_search_tree.do_global_search(
            search_term,
            user,
            specter_regtest_configured.hide_sensitive_info,
            specter_regtest_configured.wallet_manager.wallets,
            specter_regtest_configured.device_manager.devices,
        )
        assert results["search_term"] == search_term

        expectation = {
            "value": address["address"],
            "title": f"Change #{i}",
            "key": "Address",
            "click_action": {
                "url": f"wallets_endpoint/addresses_with_type/{unfunded_hot_wallet_1.alias}/change",
                "method_str": "form",
                "form_data": {
                    "action": "show_address_on_load",
                    "address_dict": f'{{"index": {i}, "address": "{address["address"]}", "label": "Change #{i}", "amount": 0, "used": false, "utxo": 0, "type": "change", "service_id": null}}',
                },
            },
        }
        assert len(results["result_dicts"]) == 1
        assert len(results["result_dicts"][0]["search_results"]) == 1
        assert results["result_dicts"][0]["search_results"][0] == expectation

    # receive addresses
    addresses = unfunded_hot_wallet_1.addresses_info(is_change=False)
    logger.info(f"Searching for  {len(addresses)} receive addresses")
    assert addresses
    for i, address in enumerate(addresses):
        search_term = address["address"].upper()  # checks the case insensitive search
        results = global_search_tree.do_global_search(
            search_term,
            user,
            specter_regtest_configured.hide_sensitive_info,
            specter_regtest_configured.wallet_manager.wallets,
            specter_regtest_configured.device_manager.devices,
        )

        assert results["search_term"] == search_term

        expectation = {
            "value": address["address"],
            "title": f"Address #{i}",
            "key": "Address",
            "click_action": {
                "url": f"wallets_endpoint/addresses_with_type/{unfunded_hot_wallet_1.alias}/receive",
                "method_str": "form",
                "form_data": {
                    "action": "show_address_on_load",
                    "address_dict": f'{{"index": {i}, "address": "{address["address"]}", "label": "Address #{i}", "amount": 0, "used": false, "utxo": 0, "type": "receive", "service_id": null}}',
                },
            },
        }

        assert (
            len(results["result_dicts"]) == 2
            if unfunded_hot_wallet_1.address == address["address"]
            else 1
        )
        assert len(results["result_dicts"][0]["search_results"]) == 1
        # the expectation can be in results["result_dicts"][0]["search_results"][0] or in results["result_dicts"][1]["search_results"][0]
        assert expectation in [
            result_dict["search_results"][0] for result_dict in results["result_dicts"]
        ]


@patch("cryptoadvance.specter.global_search.url_for", mock_url_for)
@patch("cryptoadvance.specter.global_search._", str)
def test_devices(specter_regtest_configured: Specter, unfunded_hot_wallet_1):
    user = specter_regtest_configured.user_manager.user
    global_search_tree = GlobalSearchTree()

    # change addresses
    devices = specter_regtest_configured.device_manager.devices.values()
    assert devices
    for device in devices:
        logger.info(f"Searching for  {len(device.keys)} keys in device {device.alias}")

        search_term = device.alias[3:8]
        results = global_search_tree.do_global_search(
            search_term,
            user,
            specter_regtest_configured.hide_sensitive_info,
            specter_regtest_configured.wallet_manager.wallets,
            specter_regtest_configured.device_manager.devices,
        )
        assert len(results["result_dicts"][0]["search_results"]) == 2
        assert results["result_dicts"][0]["search_results"][0]["key"] == "Alias"
        assert results["result_dicts"][0]["search_results"][0]["value"] == device.alias
        assert results["result_dicts"][0]["search_results"][1]["key"] == "Name"
        assert results["result_dicts"][0]["search_results"][1]["value"] == device.name

        for key in device.keys:
            search_term = key.original
            results = global_search_tree.do_global_search(
                search_term,
                user,
                specter_regtest_configured.hide_sensitive_info,
                specter_regtest_configured.wallet_manager.wallets,
                specter_regtest_configured.device_manager.devices,
            )
            assert len(results["result_dicts"][0]["search_results"]) == 1
            assert (
                search_term in results["result_dicts"][0]["search_results"][0]["value"]
            )
            assert (
                key.fingerprint
                in results["result_dicts"][0]["search_results"][0]["value"]
            )
