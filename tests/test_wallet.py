import json, logging, pytest, time, os
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.managers.wallet_manager import WalletManager
from cryptoadvance.specter.wallet import Wallet
from conftest import instantiate_bitcoind_controller

logger = logging.getLogger(__name__)


def test_import_address_labels(caplog, specter_regtest_configured):
    caplog.set_level(logging.INFO)

    specter = specter_regtest_configured
    # Create a new device that can sign psbts (Bitcoin Core hot wallet)
    device = specter.device_manager.add_device(
        name="bitcoin_core_hot_wallet", device_type="bitcoincore", keys=[]
    )
    device.setup_device(file_password=None, wallet_manager=specter.wallet_manager)
    device.add_hot_wallet_keys(
        mnemonic="abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about",
        passphrase="",
        paths=["m/49h/0h/0h"],
        file_password=None,
        wallet_manager=specter.wallet_manager,
        testnet=True,
        keys_range=[0, 1000],
        keys_purposes=[],
    )

    wallet: Wallet = specter.wallet_manager.create_wallet(
        "bitcoincore_test_wallet", 1, "sh-wpkh", [device.keys[0]], [device]
    )

    # Fund the wallet. Going to need a LOT of utxos to play with.
    logger.info("Generating utxos to wallet")
    test_address = wallet.getnewaddress()  # 2NCSZrX49HHyzUy6oj8ggm9WD19hFvjzzou

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

    # _transactions is a Dict where the key is the txID and the value is a TxItem
    mytxitem = (
        wallet._transactions[
            "51dc63b8ed240a070ff1233572058bdd91072e751c5b4270fd5fea56b7a0acc8"
        ]
        == None
    )

    assert wallet.txlist()[0]["blockheight"] != None
    assert wallet.txlist()[0]["blocktime"] != None
