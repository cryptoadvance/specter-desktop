import logging
import os
from cryptoadvance.specter.util.shell import which
from cryptoadvance.specter.bitcoind import BitcoindPlainController
from cryptoadvance.specter.bitcoind import BitcoindDockerController
from cryptoadvance.specter.bitcoind import fetch_wallet_addresses_for_mining


def test_bitcoinddocker_running(caplog, docker, request):
    # TODO: Refactor this to use conftest.instantiate_bitcoind_controller
    # to reduce redundant code?
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    requested_version = request.config.getoption("--bitcoind-version")
    if docker:
        my_bitcoind = BitcoindDockerController(
            rpcport=18999, docker_tag=requested_version
        )  # completly different port to not interfere
    else:
        if os.path.isfile("tests/bitcoin/src/bitcoind"):
            # copied from conftest.py
            # always prefer the self-compiled bitcoind if existing
            my_bitcoind = BitcoindPlainController(
                bitcoind_path="tests/bitcoin/src/bitcoind"
            )
        else:
            try:
                which("bitcoind")
                my_bitcoind = BitcoindPlainController()
            except:
                # Skip this test as bitcoind is not available
                # Doesn't make sense to print anything as this won't be shown
                # for passing tests
                raise Exception("bitcoind not available")

    rpcconn = my_bitcoind.start_bitcoind(cleanup_at_exit=True, cleanup_hard=True)
    requested_version = request.config.getoption("--bitcoind-version")
    assert my_bitcoind.version() == requested_version
    assert rpcconn.get_rpc() != None
    assert rpcconn.get_rpc().ipaddress != None
    bci = rpcconn.get_rpc().getblockchaininfo()
    assert bci["blocks"] == 100
    # you can use the testcoin_faucet:
    random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
    my_bitcoind.testcoin_faucet(random_address, amount=25, mine_tx=True)
    my_bitcoind.stop_bitcoind()


def test_fetch_wallet_addresses_for_mining(caplog, wallets_filled_data_folder):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    # Todo: instantiate a specter-testwallet
    addresses = fetch_wallet_addresses_for_mining(wallets_filled_data_folder)
    assert addresses  # make more sense out of this test
