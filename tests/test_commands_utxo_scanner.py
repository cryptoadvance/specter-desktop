import logging
from random import randint
import time
import pytest
import requests
from cryptoadvance.specter.commands.utxo_scanner import UtxoScanner
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.wallet import Wallet
from fix_devices_and_wallets import create_hot_wallet_device, create_hot_segwit_wallet


@pytest.mark.skip()
def test_rescan_utxo(specter_testnet_configured: Specter, caplog):
    caplog.set_level(logging.DEBUG)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
    specter: Specter = specter_testnet_configured
    is_pruned_node = specter.rpc.getblockchaininfo()["pruned"]
    assert is_pruned_node

    # You should not change the UTXO-Set of this wallet ... ever!
    # Satoshi himself will punish you if you ever move these UTXOs !
    hot_device = create_hot_wallet_device(
        specter_testnet_configured,
        "hold_accident" + str(randint(0, 100000)),
        11 * "hold " + "accident",
    )
    assert hot_device
    wallet: Wallet = create_hot_segwit_wallet(
        specter_testnet_configured, hot_device, "hold_accident"
    )

    if is_pruned_node:

        # The pruned node on testnet might have incredible lots of TXs
        mycmd = UtxoScanner(wallet, requests.session())
        mycmd.execute(asyncc=False)
        # check_utxo is not part of the execution (but maybe should?!).
        # It's usually called from the server_endpoints
        wallet.check_utxo()
        utxos = wallet.full_utxo
        assert len(utxos) == 6
        # assert_exact_utxo_set(utxos)

        # When the txs are no longer in th pruned-set, this should work:
        # With an explorer, it should work on a pruned_node:
        mycmd = UtxoScanner(
            wallet, requests.session(), explorer="https://mempool.space/testnet/"
        )
        mycmd.execute(asyncc=False)
        utxos = wallet.full_utxo
        assert len(utxos) == 6
        assert_exact_utxo_set(utxos)

    else:
        # With a full node, you don't need any explorer
        mycmd = UtxoScanner(wallet)
        mycmd.execute(asyncc=False)
        utxos = wallet.full_utxo
        assert len(utxos) == 6
        assert_exact_utxo_set(utxos)

    assert False


def assert_exact_utxo_set(utxos):
    assert len(utxos) == 6
    assert (utxos[0]["address"], utxos[0]["amount"]) == (
        "tb1q2e5eev0wpz72eew7g5ypl0xeg38sm6tx2z50nm",
        0.00020745,
    )
    assert (utxos[1]["address"], utxos[1]["amount"]) == (
        "tb1qs74297wdnd0wmztekcmz3wnd6f6c3gljuhj56v",
        0.00039557,
    )
    assert (utxos[2]["address"], utxos[2]["amount"]) == (
        "tb1qk4e29xa2cxxy02yq6glpwet6hkgdcjfz8gnnwk",
        0.00209453,
    )
    assert (utxos[3]["address"], utxos[3]["amount"]) == (
        "tb1q7uqexf8yhcvcx04trf5cx0cls53jyq8lynsmns",
        0.00231033,
    )
    assert (utxos[4]["address"], utxos[4]["amount"]) == (
        "tb1q9lgm78033652xt0e0t3yqzjlu9uzf0fdwpelkq",
        0.0008,
    )
    assert (utxos[5]["address"], utxos[5]["amount"]) == (
        "tb1qhxrx4nyxfesq3vp9rrae6q8zxsayl6ndwmhmv0",
        0.0006,
    )
