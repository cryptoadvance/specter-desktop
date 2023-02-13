import json
import logging
from decimal import Decimal

import pytest
from cryptoadvance.specter.helpers import alias
from cryptoadvance.specter.managers.wallet_manager import WalletManager
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.util.mnemonic import generate_mnemonic


def test_alias():
    assert alias("wurst 1") == "wurst_1"
    assert alias("wurst_1") == "wurst_1"
    assert alias("Wurst$ 1") == "wurst_1"


def test_specter(specter_regtest_configured, caplog):
    caplog.set_level(logging.DEBUG)
    specter_regtest_configured.check()
    assert specter_regtest_configured.wallet_manager is not None
    assert specter_regtest_configured.device_manager is not None
    assert specter_regtest_configured.node.host != "None"
    logging.debug("out {}".format(specter_regtest_configured.node.test_rpc()))
    json_return = json.loads(specter_regtest_configured.node.test_rpc()["out"])
    # that might only work if your chain is fresh
    # assert json_return['blocks'] == 100
    assert json_return["chain"] == "regtest"


@pytest.mark.slow
def test_abandon_purged_tx(caplog, request, devices_filled_data_folder, device_manager):
    # Specter should support calling abandontransaction if a pending tx has been purged
    # from the mempool. Test starts a new bitcoind with a restricted mempool to make it
    # easier to spam the mempool and purge our target tx.
    # TODO: Similar test but for maxmempoolexpiry?

    # Copied and adapted from:
    #    https://github.com/bitcoin/bitcoin/blob/master/test/functional/mempool_limit.py
    from bitcoin_core.test.functional.test_framework.util import (
        create_lots_of_big_transactions,
        gen_return_txouts,
        satoshi_round,
    )
    from conftest import instantiate_bitcoind_controller

    caplog.set_level(logging.DEBUG)

    # ==== Specter-specific: do custom setup ====
    # Instantiate a new bitcoind w/limited mempool. Use a different port to not interfere
    # with existing instance for other tests.
    bitcoind_controller = instantiate_bitcoind_controller(
        request,
        rpcport=18998,
        extra_args=["-acceptnonstdtxn=1", "-maxmempool=5", "-spendzeroconfchange=0"],
    )
    try:
        assert bitcoind_controller.get_rpc().test_connection()
        rpcconn = bitcoind_controller.rpcconn
        rpc = rpcconn.get_rpc()
        assert rpc is not None
        assert rpc.ipaddress != None

        # Note: Our utxo creation is simpler than mempool_limit.py's approach since we're
        # running in regtest and can just use generatetoaddress().

        # Instantiate a new Specter instance to talk to this bitcoind
        config = {
            "rpc": {
                "autodetect": False,
                "datadir": "",
                "user": rpcconn.rpcuser,
                "password": rpcconn.rpcpassword,
                "port": rpcconn.rpcport,
                "host": rpcconn.ipaddress,
                "protocol": "http",
            },
            "auth": {
                "method": "rpcpasswordaspin",
            },
        }
        specter = Specter(
            data_folder=devices_filled_data_folder, config=config, checker_threads=False
        )
        specter.check()

        assert specter.info["mempool_info"]["maxmempool"] == 5 * 1000 * 1000  # 5MB

        # Largely copy-and-paste from test_wallet_manager.test_wallet_createpsbt.
        # TODO: Make a test fixture in conftest.py that sets up already funded wallets
        # for a bitcoin core hot wallet.
        wallet_manager = WalletManager(
            devices_filled_data_folder,
            rpc,
            "regtest",
            device_manager,
        )

        # Create a new device that can sign psbts (Bitcoin Core hot wallet)
        device = device_manager.add_device(
            name="bitcoin_core_hot_wallet", device_type="bitcoincore", keys=[]
        )
        device.setup_device(file_password=None, wallet_manager=wallet_manager)
        device.add_hot_wallet_keys(
            mnemonic=generate_mnemonic(strength=128),
            passphrase="",
            paths=["m/84h/1h/0h", "m/84h/1h/1h"],
            file_password=None,
            wallet_manager=wallet_manager,
            testnet=True,
            keys_range=[0, 1000],
            keys_purposes=[],
        )

        wallet = wallet_manager.create_wallet(
            "bitcoincore_test_wallet", 1, "wpkh", [device.keys[0]], [device]
        )
        # dummy wallet that will do the mining
        dummy = wallet_manager.create_wallet(
            "bitcoincore_dummy", 1, "wpkh", [device.keys[1]], [device]
        )

        # Fund the wallet. Going to need a LOT of utxos to play with.
        logging.info("Generating utxos to wallet")
        address = wallet.getnewaddress()
        wallet.rpc.generatetoaddress(1, address)
        dummy_address = dummy.getnewaddress()
        dummy.rpc.generatetoaddress(90, dummy_address)

        # newly minted coins need 100 blocks to get spendable
        # let's mine another 100 blocks to get these coins spendable
        dummy.rpc.generatetoaddress(101, dummy_address)

        # update the wallet data
        wallet.update_balance()
        dummy.update_balance()

        # ==== Begin test from mempool_limit.py ====
        txouts = gen_return_txouts()
        relayfee = satoshi_round(rpc.getnetworkinfo()["relayfee"])

        logging.info("Check that mempoolminfee is minrelytxfee")
        assert satoshi_round(rpc.getmempoolinfo()["minrelaytxfee"]) == Decimal(
            "0.00001000"
        )
        assert satoshi_round(rpc.getmempoolinfo()["mempoolminfee"]) == Decimal(
            "0.00001000"
        )

        utxos = wallet.rpc.listunspent()

        logging.info("Create a mempool tx that will be evicted")
        us0 = utxos.pop()
        inputs = [{"txid": us0["txid"], "vout": us0["vout"]}]
        outputs = {wallet.getnewaddress(): 0.0001}
        tx = wallet.rpc.createrawtransaction(inputs, outputs)
        wallet.rpc.settxfee(str(relayfee))  # specifically fund this tx with low fee
        txF = wallet.rpc.fundrawtransaction(tx, {"change_type": "bech32"})
        wallet.rpc.settxfee(0)  # return to automatic fee selection
        psbtF = wallet.rpc.converttopsbt(txF["hex"])
        psbtFF = wallet.rpc.walletprocesspsbt(psbtF)
        signed = device.sign_psbt(psbtFF["psbt"], wallet)
        assert signed["complete"]
        finalized = wallet.rpc.finalizepsbt(signed["psbt"])
        txid = wallet.rpc.sendrawtransaction(finalized["hex"])

        # ==== Specter-specific: can't abandon a valid pending tx ====
        try:
            wallet.abandontransaction(txid)
        except SpecterError as e:
            assert "Cannot abandon" in str(e)

        # ==== Resume test from mempool_limit.py ====
        # Spam the mempool with big transactions!
        txids = []
        dummy_utxos = dummy.rpc.listunspent()
        relayfee = satoshi_round(rpc.getnetworkinfo()["relayfee"])
        base_fee = float(relayfee) * 100
        for i in range(3):
            txids.append([])
            txids[i] = create_lots_of_big_transactions(
                dummy, txouts, dummy_utxos[30 * i : 30 * i + 30], 30, (i + 1) * base_fee
            )

        logging.info("The tx should be evicted by now")
        assert txid not in wallet.rpc.getrawmempool()
        txdata = wallet.rpc.gettransaction(txid)
        assert txdata["confirmations"] == 0  # confirmation should still be 0

        # ==== Specter-specific: Verify purge and abandon ====
        assert wallet.is_tx_purged(txid)
        wallet.abandontransaction(txid)

        # tx will still be in the wallet but marked "abandoned"
        txdata = wallet.rpc.gettransaction(txid)
        for detail in txdata["details"]:
            if detail["category"] == "send":
                assert detail["abandoned"]

        # at this point we should have all the balance in trusted
        # nothing in untrusted
        untrusted = wallet.update_balance()["untrusted_pending"]
        assert untrusted == 0
        # Can we now spend those same inputs?
        outputs = {wallet.getnewaddress(): 0.0001}
        tx = wallet.rpc.createrawtransaction(inputs, outputs)

        # Fund this tx with a high enough fee
        relayfee = satoshi_round(rpc.getnetworkinfo()["relayfee"])
        wallet.rpc.settxfee(str(relayfee * Decimal("3.0")))

        txF = wallet.rpc.fundrawtransaction(tx)
        wallet.rpc.settxfee(0)  # return to automatic fee selection
        psbtF = wallet.rpc.converttopsbt(txF["hex"])
        psbtFF = wallet.rpc.walletprocesspsbt(psbtF)
        signed = device.sign_psbt(psbtFF["psbt"], wallet)
        assert signed["complete"]
        finalized = wallet.rpc.finalizepsbt(signed["psbt"])
        txid = wallet.rpc.sendrawtransaction(finalized["hex"])

        # Should have been accepted by the mempool
        assert txid in wallet.rpc.getrawmempool()
        # Our balance should go to untrusted now as it's unconfirmed
        assert wallet.update_balance()["untrusted_pending"] > 0
    finally:
        # Clean up
        bitcoind_controller.stop_bitcoind()
