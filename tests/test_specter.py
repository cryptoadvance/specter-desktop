import json, logging, pytest
from cryptoadvance.specter.helpers import alias, generate_mnemonic
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.rpc import BitcoinRPC
from cryptoadvance.specter.specter import get_rpc, Specter
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


def test_detect_purged_tx(
    caplog, docker, request, devices_filled_data_folder, device_manager
):
    # Specter should detect that a tx with a low fee has been purged from the mempool
    # and should be abandoned by the wallet. Test starts a new bitcoind with a restricted
    # mempool to make it easier to spam the mempool and purge our target tx.
    from conftest import instantiate_bitcoind_controller

    caplog.set_level(logging.DEBUG)

    # Instantiate a new bitcoind w/limited mempool. Use a different port to not interfere
    # with existing instance for other tests.
    bitcoind_controller = instantiate_bitcoind_controller(
        docker, request, rpcport=18998, extra_args="-maxmempool=5"
    )
    rpcconn = bitcoind_controller.rpcconn
    rpc = rpcconn.get_rpc()
    assert rpc is not None
    assert rpc.ipaddress != None
    bci = rpc.getblockchaininfo()
    assert bci["blocks"] == 100

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
    address = wallet.getnewaddress()
    wallet.rpc.generatetoaddress(200, address)

    # newly minted coins need 100 blocks to get spendable
    # let's mine another 100 blocks to get these coins spendable
    wallet.rpc.generatetoaddress(101, address)

    # update the wallet data
    wallet.get_balance()

    def generate_and_broadcast_psbt(recipient_address, amount, fee_rate, unspent):
        selected_coins = [
            ", ".join([unspent["txid"], str(unspent["vout"]), "%.8f" % amount])
        ]
        psbt = wallet.createpsbt(
            addresses=[recipient_address],
            amounts=[amount],
            subtract_from=True,
            fee_rate=fee_rate,  # sats/vB
            selected_coins=selected_coins,
            rbf=True,
            existing_psbt=None,
        )
        txid = psbt["tx"]["txid"]

        # Sign the psbt with the hot wallet
        b64psbt = wallet.pending_psbts[psbt["tx"]["txid"]]["base64"]
        signed_psbt = device.sign_psbt(b64psbt, wallet, file_password=None)

        # Finalize and broadcast the signed psbt
        combined = specter.combine([signed_psbt["psbt"]])
        raw = specter.finalize(combined)
        specter.broadcast(raw["hex"])
        wallet.delete_pending_psbt(txid)

    # Make an initial tx with a very low fee_rate
    recipient_address = wallet.getnewaddress()
    generate_and_broadcast_psbt(
        recipient_address,
        amount=5.0,
        fee_rate=1.0,
        unspent=wallet.rpc.listunspent(0)[0],
    )

    # Now we need to spam the mempool with more than 5MB worth of transactions!
    spam_address = wallet.getnewaddress()  # Just keep sending to same addr
    for index, unspent in enumerate(wallet.rpc.listunspent()):
        if index == 0:
            continue

        generate_and_broadcast_psbt(
            spam_address, amount=1.0, fee_rate=80.0, unspent=unspent
        )

        if index % 10 == 0:
            specter.check_node_info()
            print(specter._info["mempool_info"])

    # Clean up
    bitcoind_controller.stop_bitcoind()
