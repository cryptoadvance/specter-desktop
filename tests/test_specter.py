import json, logging, pytest
from decimal import Decimal
from cryptoadvance.specter.helpers import alias, generate_mnemonic
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.rpc import BitcoinRPC
from cryptoadvance.specter.specter import get_rpc, Specter
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.wallet_manager import WalletManager


def test_alias():
    assert alias("wurst 1") == "wurst_1"
    assert alias("wurst_1") == "wurst_1"
    assert alias("Wurst$ 1") == "wurst_1"


@pytest.mark.skip(reason="no idea why this does not pass on gitlab exclusively")
def test_get_rpc(specter_regtest_configured):
    specter_regtest_configured.check()
    rpc_config_data = {
        "autodetect": False,
        "user": "bitcoin",
        "password": "secret",
        "port": specter_regtest_configured.config["rpc"]["port"],
        "host": "localhost",
        "protocol": "http",
    }
    print("rpc_config_data: {}".format(rpc_config_data))
    rpc = get_rpc(rpc_config_data)
    assert rpc.getblockchaininfo()
    assert isinstance(rpc, BitcoinRPC)
    # ToDo test autodetection-features


def test_specter(specter_regtest_configured, caplog):
    caplog.set_level(logging.DEBUG)
    specter_regtest_configured.check()
    assert specter_regtest_configured.wallet_manager is not None
    assert specter_regtest_configured.device_manager is not None
    assert specter_regtest_configured.config["rpc"]["host"] != "None"
    logging.debug("out {}".format(specter_regtest_configured.test_rpc()))
    json_return = json.loads(specter_regtest_configured.test_rpc()["out"])
    # that might only work if your chain is fresh
    # assert json_return['blocks'] == 100
    assert json_return["chain"] == "regtest"


def test_abandon_purged_tx(
    caplog, docker, request, devices_filled_data_folder, device_manager
):
    # Specter should support calling abandontransaction if a pending tx has been purged
    # from the mempool. Test starts a new bitcoind with a restricted mempool to make it
    # easier to spam the mempool and purge our target tx.
    # TODO: Similar test but for maxmempoolexpiry?

    # Copied and adapted from:
    #    https://github.com/bitcoin/bitcoin/blob/master/test/functional/mempool_limit.py
    from bitcoin_core.test.functional.test_framework.util import (
        gen_return_txouts,
        satoshi_round,
        create_lots_of_big_transactions,
    )
    from conftest import instantiate_bitcoind_controller

    caplog.set_level(logging.DEBUG)

    # ==== Specter-specific: do custom setup ====
    # Instantiate a new bitcoind w/limited mempool. Use a different port to not interfere
    # with existing instance for other tests.
    bitcoind_controller = instantiate_bitcoind_controller(
        docker,
        request,
        rpcport=18998,
        extra_args=["-acceptnonstdtxn=1", "-maxmempool=5", "-spendzeroconfchange=0"],
    )
    rpcconn = bitcoind_controller.rpcconn
    rpc = rpcconn.get_rpc()
    assert rpc is not None
    assert rpc.ipaddress != None
    bci = rpc.getblockchaininfo()
    assert bci["blocks"] == 100

    # Note: Our utxo creation is simpler than mempool_limit.py's approach since we're
    # running in regtest and can just use generatetoaddress().

    # Instantiate a new Specter instance to talk to this bitcoind
    config = {
        "rpc": {
            "autodetect": False,
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
    specter = Specter(data_folder=devices_filled_data_folder, config=config)
    specter.check()

    specter.check_node_info()
    assert specter._info["mempool_info"]["maxmempool"] == 5 * 1000 * 1000  # 5MB

    # Largely copy-and-paste from test_wallet_manager.test_wallet_createpsbt.
    # TODO: Make a test fixture in conftest.py that sets up already funded wallets
    # for a bitcoin core hot wallet.
    wallet_manager = WalletManager(
        200100,
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
        paths=["m/49h/0h/0h"],
        file_password=None,
        wallet_manager=wallet_manager,
        testnet=True,
        keys_range=[0, 1000],
        keys_purposes=[],
    )

    wallet = wallet_manager.create_wallet(
        "bitcoincore_test_wallet", 1, "sh-wpkh", [device.keys[0]], [device]
    )

    # Fund the wallet. Going to need a LOT of utxos to play with.
    logging.info("Generating utxos to wallet")
    address = wallet.getnewaddress()
    wallet.rpc.generatetoaddress(91, address)

    # newly minted coins need 100 blocks to get spendable
    # let's mine another 100 blocks to get these coins spendable
    wallet.rpc.generatetoaddress(101, address)

    # update the wallet data
    wallet.get_balance()

    # ==== Begin test from mempool_limit.py ====
    txouts = gen_return_txouts()
    relayfee = satoshi_round(rpc.getnetworkinfo()["relayfee"])

    logging.info("Check that mempoolminfee is minrelytxfee")
    assert satoshi_round(rpc.getmempoolinfo()["minrelaytxfee"]) == Decimal("0.00001000")
    assert satoshi_round(rpc.getmempoolinfo()["mempoolminfee"]) == Decimal("0.00001000")

    txids = []
    utxos = wallet.rpc.listunspent()

    logging.info("Create a mempool tx that will be evicted")
    us0 = utxos.pop()
    inputs = [{"txid": us0["txid"], "vout": us0["vout"]}]
    outputs = {wallet.getnewaddress(): 0.0001}
    tx = wallet.rpc.createrawtransaction(inputs, outputs)
    wallet.rpc.settxfee(str(relayfee))  # specifically fund this tx with low fee
    txF = wallet.rpc.fundrawtransaction(tx)
    wallet.rpc.settxfee(0)  # return to automatic fee selection
    txFS = device.sign_raw_tx(txF["hex"], wallet)
    txid = wallet.rpc.sendrawtransaction(txFS["hex"])

    # ==== Specter-specific: can't abandon a valid pending tx ====
    try:
        wallet.abandontransaction(txid)
    except SpecterError as e:
        assert "Cannot abandon" in str(e)

    # ==== Resume test from mempool_limit.py ====
    # Spam the mempool with big transactions!
    relayfee = satoshi_round(rpc.getnetworkinfo()["relayfee"])
    base_fee = float(relayfee) * 100
    for i in range(3):
        txids.append([])
        txids[i] = create_lots_of_big_transactions(
            wallet, txouts, utxos[30 * i : 30 * i + 30], 30, (i + 1) * base_fee
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

    # Can we now spend those same inputs?
    outputs = {wallet.getnewaddress(): 0.0001}
    tx = wallet.rpc.createrawtransaction(inputs, outputs)

    # Fund this tx with a high enough fee
    relayfee = satoshi_round(rpc.getnetworkinfo()["relayfee"])
    wallet.rpc.settxfee(str(relayfee * Decimal("3.0")))

    txF = wallet.rpc.fundrawtransaction(tx)
    wallet.rpc.settxfee(0)  # return to automatic fee selection
    txFS = device.sign_raw_tx(txF["hex"], wallet)
    txid = wallet.rpc.sendrawtransaction(txFS["hex"])

    # Should have been accepted by the mempool
    assert txid in wallet.rpc.getrawmempool()
    assert wallet.get_balance()["untrusted_pending"] == 0.0001

    # Clean up
    bitcoind_controller.stop_bitcoind()
