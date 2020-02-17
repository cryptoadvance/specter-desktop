from cryptoadvance.specter.bitcoind import fetch_wallet_addresses_for_mining

def test_fetch_wallet_addresses_for_mining(wallets_filled_data_folder):
    # Todo: instantiate a specter-testwallet
    addresses = fetch_wallet_addresses_for_mining(wallets_filled_data_folder)
    assert addresses # make more sense out of this test
