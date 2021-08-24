import json, logging, pytest, time, os
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.managers.wallet_manager import WalletManager
from conftest import instantiate_bitcoind_controller

logger = logging.getLogger(__name__)


@pytest.mark.slow
def test_electrum_label_import(
    caplog, docker, request, devices_filled_data_folder, device_manager
):
    caplog.set_level(logging.DEBUG)

    # ==== Specter-specific: do custom setup ====
    # Instantiate a new bitcoind w/limited mempool. Use a different port to not interfere
    # with existing instance for other tests.
    bitcoind_controller = instantiate_bitcoind_controller(
        docker,
        request,
        rpcport=18968,
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

        # Largely copy-and-paste from test_wallet_manager.test_wallet_createpsbt.
        # TODO: Make a test fixture in conftest.py that sets up already funded wallets
        # for a bitcoin core hot wallet.
        wallet_manager = WalletManager(
            200100,
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
            mnemonic="abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about",
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
        logger.info("Generating utxos to wallet")
        test_address = wallet.getnewaddress()

        wallet.rpc.generatetoaddress(1, test_address)[0]

        # newly minted coins need 100 blocks to get spendable
        # let's mine another 100 blocks to get these coins spendable
        trash_address = wallet.getnewaddress()
        wallet.rpc.generatetoaddress(100, trash_address)

        # the utxo is only available after the 100 mined blocks
        utxos = wallet.rpc.listunspent()
        # txid of the funding of test_address
        txid = utxos[0]["txid"]

        assert wallet._addresses[test_address]["label"] is None
        number_of_addresses = len(wallet._addresses)

        # Test it with a txid label that does not belong to the wallet -> should be ignored
        print(
            wallet.import_electrum_label_export(
                json.dumps(
                    {
                        "8d0958cb8701fac7421eb077e44b36809b90c7ad4a35e0c607c2cd591c522668": "txid label"
                    }
                )
            )
        )
        assert wallet._addresses[test_address]["label"] is None
        assert len(wallet._addresses) == number_of_addresses

        # Test it with an address label that does not belong to the wallet -> should be ignored
        print(
            wallet.import_electrum_label_export(
                json.dumps({"12dRugNcdxK39288NjcDV4GX7rMsKCGn6B": "address label"})
            )
        )
        assert wallet._addresses[test_address]["label"] is None
        assert len(wallet._addresses) == number_of_addresses

        # Test it with a txid label
        print(wallet.import_electrum_label_export(json.dumps({txid: "txid label"})))
        assert wallet._addresses[test_address]["label"] == "txid label"

        # The txid label should now be replaced by the address label
        print(
            wallet.import_electrum_label_export(
                json.dumps({test_address: "address label"})
            )
        )
        assert wallet._addresses[test_address]["label"] == "address label"

    finally:
        # Clean up
        bitcoind_controller.stop_bitcoind()
