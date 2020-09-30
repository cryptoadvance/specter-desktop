import logging
from cryptoadvance.specter.bitcoind import fetch_wallet_addresses_for_mining


def test_fetch_wallet_addresses_for_mining(caplog, wallets_filled_data_folder):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    # Todo: instantiate a specter-testwallet
    addresses = fetch_wallet_addresses_for_mining(wallets_filled_data_folder)
    assert addresses  # make more sense out of this test
