import json, logging, pytest, time, os
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.wallet import Wallet
from cryptoadvance.specter.managers.wallet_manager import WalletManager

logger = logging.getLogger(__name__)


def test_import_address_labels(
    caplog, specter_regtest_configured: Specter, funded_hot_wallet_1: Wallet
):
    caplog.set_level(logging.DEBUG)
    wallet = funded_hot_wallet_1

    # the utxo is only available after the 100 mined blocks
    utxos = wallet.rpc.listunspent()
    logger.debug(f"these are the utxos: {utxos}.")
    # txid of the funding of test_address
    txid = utxos[0]["txid"]
    logger.debug(f"this is the txid: {txid}.")
    test_address = utxos[0]["address"]
    logger.debug(f"these are the addresses: {wallet.addresses}.")
    logger.debug(f"these are the _addresses: {wallet._addresses}.")
    assert wallet._addresses[test_address]["label"] is None
    number_of_addresses = len(wallet._addresses)

    # Electrum
    # Test it with a txid label that does not belong to the wallet -> should be ignored
    wallet.import_address_labels(
        json.dumps(
            {
                "8d0958cb8701fac7421eb077e44b36809b90c7ad4a35e0c607c2cd591c522668": "txid label"
            }
        )
    )
    assert wallet._addresses[test_address]["label"] is None
    assert len(wallet._addresses) == number_of_addresses

    # Test it with an address label that does not belong to the wallet -> should be ignored
    wallet.import_address_labels(
        json.dumps({"12dRugNcdxK39288NjcDV4GX7rMsKCGn6B": "address label"})
    )
    assert wallet._addresses[test_address]["label"] is None
    assert len(wallet._addresses) == number_of_addresses

    # Test it with a txid label
    wallet.import_address_labels(json.dumps({txid: "txid label"}))
    assert wallet._addresses[test_address]["label"] == "txid label"

    # The txid label should now be replaced by the address label
    wallet.import_address_labels(json.dumps({test_address: "address label"}))
    assert wallet._addresses[test_address]["label"] == "address label"

    # Specter JSON
    wallet._addresses[test_address].set_label("some_fancy_label_json")
    specter_json = json.dumps(wallet.to_json(for_export=True))
    wallet._addresses[test_address].set_label("label_got_lost")
    wallet.import_address_labels(specter_json)
    assert wallet._addresses[test_address]["label"] == "some_fancy_label_json"

    # Specter CSV
    csv_string = f"""Index,Address,Type,Label,Used,UTXO,Amount (BTC)
    0,{test_address},receive,some_fancy_label_csv,Yes,0,0"""
    wallet._addresses[test_address].set_label("label_got_lost")
    wallet.import_address_labels(csv_string)
    assert wallet._addresses[test_address]["label"] == "some_fancy_label_csv"
