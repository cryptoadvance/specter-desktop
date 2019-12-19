from cli import fetch_wallet_addresses_for_mining

def test_fetch_wallet_addresses_for_mining():
    # Todo: instantiate a specter-testwallet
    addresses = fetch_wallet_addresses_for_mining()
    assert addresses # make more sense out of this test
