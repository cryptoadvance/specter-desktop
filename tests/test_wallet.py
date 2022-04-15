import json, logging, pytest, time, os
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.managers.wallet_manager import WalletManager
from cryptoadvance.specter.wallet import Wallet
from conftest import instantiate_bitcoind_controller

logger = logging.getLogger(__name__)


def test_check_utxo_and_amounts(
    specter_regtest_configured: Specter, funded_hot_wallet_1: Wallet
):
    wl = funded_hot_wallet_1
    # Let's first prepare some locked txids
    unspent_list_orig = wl.rpc.listunspent()  # to be able to ref in stable way
    wl.check_utxo()
    # 10 transactions + 2 unconfirmed
    assert len(wl.full_utxo) == 12
    # none are locked
    assert len([tx for tx in wl.full_utxo if tx["locked"]]) == 0
    # Freeze 2 UTXO
    # ["txid:vout", "txid:vout"]
    wl.toggle_freeze_utxo(
        [
            f"{unspent_list_orig[0]['txid']}:{unspent_list_orig[0]['vout']}",
            f"{unspent_list_orig[1]['txid']}:{unspent_list_orig[1]['vout']}",
        ]
    )
    # still 12 utxo with 2 unconfirmed
    wl.check_utxo()
    assert len(wl.full_utxo) == 12
    # 2 are locked
    assert len([tx for tx in wl.full_utxo if tx["locked"]]) == 2

    # Check total amount
    assert wl.amount_total == 15
    # Check confirmed amount
    assert wl.amount_confirmed == 10
    # Check unconfirmed amount
    assert wl.amount_unconfirmed == 5
    # Check frozen amount
    assert wl.amount_frozen == 2
    # Check available amount
    assert wl.amount_available == 13  # total - frozen
    # Check immature amount
    address = wl.getnewaddress()
    wl.rpc.generatetoaddress(1, address)
    wl.update_balance()
    assert (
        round(wl.amount_immature, 1) == 50
        or round(wl.amount_immature, 1) == 25
        or round(wl.amount_immature, 1) == 12.5
        or round(wl.amount_immature, 2) == 6.25
    )
    # amount_locked_unsigned is tested in test_wallet_createpsbt (in test_managers_wallet.py)
