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

    assert wallet.txlist()[0]["blockheight"] != None
    assert wallet.txlist()[0]["blocktime"] != None


def test_check_utxo(specter_regtest_configured: Specter, funded_hot_wallet_1: Wallet):
    wl = funded_hot_wallet_1

    # Let's first prepare some locked txids
    unspent_list_orig = wl.rpc.listunspent()  # to be able to ref in stable way

    wl.check_utxo()
    # 10 transactions + 2 unconfirmed
    assert len(wl.full_utxo) == 12
    for tx in wl.full_utxo:
        print(f"txid: {tx['txid']}")
    # non are locked
    assert len([tx for tx in wl.full_utxo if tx["locked"]]) == 0

    unspent_list = wl.rpc.listunspent()
    print(f"unspent_list: {len(unspent_list)}")
    print([tx["txid"] for tx in unspent_list])

    print(f"\n\nLocking this one: {unspent_list_orig[0]['txid']}")
    print(wl.rpc.gettransaction(unspent_list_orig[0]["txid"]))
    wl.rpc.lockunspent(
        False,
        [{"txid": unspent_list_orig[0]["txid"], "vout": unspent_list_orig[0]["vout"]}],
    )
    print(f"\n\nLocking this one: {unspent_list_orig[1]['txid']}")
    print(wl.rpc.gettransaction(unspent_list_orig[1]["txid"]))
    wl.rpc.lockunspent(
        False,
        [{"txid": unspent_list_orig[1]["txid"], "vout": unspent_list_orig[1]["vout"]}],
    )

    unspent_list = wl.rpc.listunspent()
    print(f"\n\nunspent_list: {len(unspent_list)}")
    print([tx["txid"] for tx in unspent_list])

    wl.check_utxo()
    # still 2 transactions + 2 unconfirmed
    for tx in wl.full_utxo:
        print(f"txid: {tx['txid']}")
    assert len(wl.full_utxo) == 12
    # 2 are locked
    assert len([tx for tx in wl.full_utxo if tx["locked"]]) == 2
