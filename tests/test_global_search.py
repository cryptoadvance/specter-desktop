from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.managers.user_manager import UserManager
from cryptoadvance.specter.wallet import Wallet
import logging

logger = logging.getLogger(__name__)
from cryptoadvance.specter.global_search import GlobalSearchTrees
from unittest.mock import MagicMock, patch
from fix_devices_and_wallets import create_hot_wallet_device, create_hot_wallet_with_ID


def mock_url_for(url, **kwargs):
    return f"{url}/".replace(".", "/") + "/".join(kwargs.values())


@patch("cryptoadvance.specter.global_search.url_for", mock_url_for)
@patch("cryptoadvance.specter.global_search._", str)
def test_check_utxo_and_amounts(
    specter_regtest_configured: Specter, funded_hot_wallet_1
):
    user = specter_regtest_configured.user_manager.user
    logger.info(funded_hot_wallet_1)
    global_search_trees = GlobalSearchTrees(user.wallet_manager, user.device_manager)

    unspent_list = (
        funded_hot_wallet_1.rpc.listunspent()
    )  # to be able to ref in stable way
    assert len(unspent_list) > 1  # otherwise the test will not test anything
    logger.info(unspent_list)

    for tx in unspent_list:
        search_term = tx["txid"].upper()  # checks the case insensitive search
        results = global_search_trees.do_global_search(
            search_term, user, specter_regtest_configured.hide_sensitive_info
        )

        logger.info(results)
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
