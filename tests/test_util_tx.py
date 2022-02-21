import json, logging, pytest
from decimal import Decimal
from cryptoadvance.specter.helpers import alias, generate_mnemonic
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.rpc import BitcoinRPC
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.managers.wallet_manager import WalletManager
from cryptoadvance.specter.util.tx import convert_rawtransaction_to_psbt


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


def test_import_raw_transaction(
    caplog,
    bitcoin_regtest: NodeController,
    specter_regtest_configured: Specter,
    hot_wallet_device_1: Device,
    hot_wallet_device_2: Device,
):

    caplog.set_level(logging.INFO)
    devices = [hot_wallet_device_1, hot_wallet_device_2]
    # device = devices[0]
    wallet_manager = specter_regtest_configured.wallet_manager

    def sign_with_devices(psbtFF, devices=devices):
        signed = psbtFF
        for device in devices:
            signed = device.sign_psbt(signed["psbt"], wallet)
            if signed["complete"]:
                break
        logging.info(f"signed  {psbtFF}")
        assert signed["complete"]
        return signed

    # Let's test that with all the relevant key-types
    for key_type in [
        "sh-wsh",  # Single (Nested)
        "wpkh",  # Single (Segwit)
        # "pkh",    # Single (Legacy)
        "wsh",  # Multisig (Segwit)
        "sh-wpkh",  # Multisig (Nested)
        # "sh",     # Multisig (Legacy)
        "tr",  # Taproot
    ]:

        logging.info(f"begin of loop key_type '{key_type}'")

        # choose the devices
        if key_type in ["sh", "wsh", "sh-wsh"]:  # multisig
            keys = [
                key
                for device in devices
                for key in device.keys
                if key.key_type == key_type
            ]
            used_devices = devices
        else:
            keys = [key for key in devices[0].keys if key.key_type == key_type]
            used_devices = [devices[0]]

        assert keys

        # create the wallet for that key-type
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

        # fund it
        bitcoin_regtest.testcoin_faucet(wallet.getnewaddress(), amount=3)
        wallet.save_to_file()

        # Create a raw TX
        outputs = {wallet.getnewaddress(): 1}
        tx = wallet.rpc.createrawtransaction([], outputs)
        txF = wallet.rpc.fundrawtransaction(
            tx, {"changeAddress": wallet.getnewaddress()}
        )
        psbtF = wallet.rpc.converttopsbt(txF["hex"])
        psbtFF = wallet.rpc.walletprocesspsbt(psbtF)
        signed = sign_with_devices(psbtFF)
        finalized_hex = wallet.rpc.finalizepsbt(signed["psbt"])["hex"]

        # convert the tx-hex to psbt
        psbt_base64 = wallet.convert_rawtransaction_to_psbt(finalized_hex)

        # Finally: check that the original TX == recreated raw_transaction
        assert finalized_hex == wallet.rpc.finalizepsbt(psbt_base64)["hex"]
