import json, logging, pytest
from decimal import Decimal
from cryptoadvance.specter.helpers import alias, generate_mnemonic
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.rpc import BitcoinRPC
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.managers.wallet_manager import WalletManager
from cryptoadvance.specter.util.tx import convert_rawtransaction_to_psbt


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
        specter = Specter(data_folder=devices_filled_data_folder, config=config)
        specter.check()

        assert specter.info["mempool_info"]["maxmempool"] == 5 * 1000 * 1000  # 5MB

        # Largely copy-and-paste from test_wallet_manager.test_wallet_createpsbt.
        # TODO: Make a test fixture in conftest.py that sets up already funded wallets
        # for a bitcoin core hot wallet.
        wallet_manager = WalletManager(
            210100,
            devices_filled_data_folder,
            rpc,
            "regtest",
            device_manager,
            allow_threading=False,
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


@pytest.mark.slow
def test_import_raw_transaction(
    caplog, docker, request, devices_filled_data_folder, device_manager
):
    from conftest import instantiate_bitcoind_controller

    caplog.set_level(logging.DEBUG)

    # ==== Specter-specific: do custom setup ====
    # Instantiate a new bitcoind w/limited mempool. Use a different port to not interfere
    # with existing instance for other tests.
    bitcoind_controller = instantiate_bitcoind_controller(
        docker,
        request,
        rpcport=18998,
    )
    try:
        assert bitcoind_controller.get_rpc().test_connection()
        rpcconn = bitcoind_controller.rpcconn
        rpc = rpcconn.get_rpc()
        assert rpc is not None
        assert rpc.ipaddress != None

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
        specter = Specter(data_folder=devices_filled_data_folder, config=config)
        specter.check()

        wallet_manager = WalletManager(
            210100,
            devices_filled_data_folder,
            rpc,
            "regtest",
            device_manager,
            allow_threading=False,
        )

        # Create a new device that can sign psbts (Bitcoin Core hot wallet)
        devices = []
        for i in range(2):
            device = device_manager.add_device(
                name=f"bitcoin_core_hot_wallet{i}", device_type="bitcoincore", keys=[]
            )
            device.setup_device(file_password=None, wallet_manager=wallet_manager)
            device.add_hot_wallet_keys(
                mnemonic=generate_mnemonic(strength=128),
                passphrase="",
                paths=[
                    "m/49h/1h/0h",  #  Single Sig (Nested)
                    "m/84h/1h/0h",  #  Single Sig (Segwit)'
                    "m/86h/1h/0h",  # Single Sig (Taproot)    #  Taproot ONLY works if this derivation path is enabled. The wallet descriptor is derived from this
                    "m/48h/1h/0h/1h",  # Multisig Sig (Nested)
                    "m/48h/1h/0h/2h",  # Multisig Sig (Segwit)
                    #                    "m/44h/0h/0h",  # pkh  single-legacy
                ],
                # "tr" signing doesnt work
                #     None: "General",
                #     "wpkh": "Single (Segwit)",
                #     "sh-wpkh": "Single (Nested)",
                #     "pkh": "Single (Legacy)",
                #     "wsh": "Multisig (Segwit)",
                #     "sh-wsh": "Multisig (Nested)",
                #     "sh": "Multisig (Legacy)",
                #     "tr": "Taproot",
                file_password=None,
                wallet_manager=wallet_manager,
                testnet=True,
                keys_range=[0, 1000],
                keys_purposes=[],
            )
            devices.append(device)
        device = devices[0]

        assert device.taproot_available(rpc)

        # funding wallet
        keys = [key for key in device.keys if key.key_type == "wpkh"]
        source_wallet = wallet_manager.create_wallet(
            "bitcoincore_source_wallet", 1, "wpkh", keys, [device]
        )

        logging.debug(
            f"source_wallet keys {[key.json for key in keys]}  wallet.account_map {source_wallet.account_map}"
        )
        # Fund the wallet.
        logging.info("Generating utxos to wallet")
        source_wallet.rpc.generatetoaddress(
            102, source_wallet.getnewaddress()
        )  # must mine +100 to make them spendable

        def sign_with_devices(psbtFF, devices=devices):
            signed = psbtFF
            for device in devices:
                signed = device.sign_psbt(signed["psbt"], wallet)
                if signed["complete"]:
                    break
            logging.info(f"signed  {psbtFF}")
            assert signed["complete"]
            return signed

        def fund_address(dest_address, source_wallet=source_wallet):
            outputs = {dest_address: 1}
            tx = source_wallet.rpc.createrawtransaction([], outputs)
            txF = source_wallet.rpc.fundrawtransaction(
                tx, {"changeAddress": dest_address}
            )
            psbtF = source_wallet.rpc.converttopsbt(txF["hex"])
            psbtFF = source_wallet.rpc.walletprocesspsbt(psbtF)
            logging.info(f"funding {dest_address} with {psbtFF}")
            signed = sign_with_devices(psbtFF)
            finalized = source_wallet.rpc.finalizepsbt(signed["psbt"])
            txid = source_wallet.rpc.sendrawtransaction(finalized["hex"])
            source_wallet.rpc.generatetoaddress(
                1, source_wallet.getnewaddress()
            )  # confirm tx

        for key_type in [
            "sh-wsh",
            "wpkh",
            #            "pkh",
            "wsh",
            "sh-wpkh",
            #            "sh",
            "tr",
        ]:
            #     None: "General",
            #     "wpkh": "Single (Segwit)",
            #     "sh-wpkh": "Single (Nested)",
            #     "pkh": "Single (Legacy)",
            #     "wsh": "Multisig (Segwit)",
            #     "sh-wsh": "Multisig (Nested)",
            #     "sh": "Multisig (Legacy)",
            #     "tr": "Taproot",
            logging.info(f"begin of loop key_type '{key_type}'")

            if key_type in ["sh", "wsh", "sh-wsh"]:  # multisig
                keys = [
                    key
                    for device in devices
                    for key in device.keys
                    if key.key_type == key_type
                ]
                used_devices = devices
            else:
                keys = [key for key in device.keys if key.key_type == key_type]
                used_devices = [device]

            assert keys

            wallet = wallet_manager.create_wallet(
                f"bitcoincore_test_wallet_{key_type}",
                len(used_devices),
                key_type,
                keys,
                used_devices,
            )

            logging.debug(
                f"created wallet key_type '{key_type}' keys {[key.json for key in keys]}  wallet.account_map {wallet.account_map}"
            )

            # Fund the wallet. Going to need a LOT of utxos to play with.
            fund_address(wallet.getnewaddress())
            wallet.save_to_file()

            outputs = {wallet.getnewaddress(): 1}
            tx = wallet.rpc.createrawtransaction([], outputs)
            txF = wallet.rpc.fundrawtransaction(
                tx, {"changeAddress": wallet.getnewaddress()}
            )
            psbtF = wallet.rpc.converttopsbt(txF["hex"])
            psbtFF = wallet.rpc.walletprocesspsbt(psbtF)
            signed = sign_with_devices(psbtFF)
            finalized = wallet.rpc.finalizepsbt(signed["psbt"])

            psbt_base64 = convert_rawtransaction_to_psbt(wallet, finalized["hex"])
            # check that the original rawt_transaction == recreated raw_transaction
            assert finalized["hex"] == wallet.rpc.finalizepsbt(psbt_base64)["hex"]
    finally:
        # Clean up
        bitcoind_controller.stop_bitcoind()
