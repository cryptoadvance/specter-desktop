import logging
import os

import pytest
from cryptoadvance.specter.process_controller.bitcoind_docker_controller import (
    BitcoindDockerController,
)
from cryptoadvance.specter.process_controller.bitcoind_controller import (
    BitcoindPlainController,
)
from cryptoadvance.specter.process_controller.elementsd_controller import (
    ElementsPlainController,
)
from cryptoadvance.specter.process_controller.node_controller import (
    NodePlainController,
    fetch_wallet_addresses_for_mining,
    find_node_executable,
)
from cryptoadvance.specter.util.shell import which

from cryptoadvance.specter.cli.cli_noded import prepare_elements_default_wallet

logger = logging.getLogger(__name__)


@pytest.mark.slow
@pytest.mark.skip("interferes with conftest fixtures")
def test_node_running_bitcoin(caplog, docker, request):
    # TODO: Refactor this to use conftest.instantiate_bitcoind_controller
    # to reduce redundant code?
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    requested_version = request.config.getoption("--bitcoind-version")
    try:
        if docker:
            my_bitcoind = BitcoindDockerController(
                rpcport=18456, docker_tag=requested_version
            )
            pass
        else:
            my_bitcoind = BitcoindPlainController(
                bitcoind_path=find_node_executable("bitcoin"),
                rpcport=18456,  # Non-standardport to not interfer
            )

        rpcconn = my_bitcoind.start_node(cleanup_at_exit=True, cleanup_hard=True)
        requested_version = request.config.getoption("--bitcoind-version")
        assert my_bitcoind.version() == requested_version
        assert rpcconn.get_rpc() != None
        assert rpcconn.get_rpc().ipaddress != None
        bci = rpcconn.get_rpc().getblockchaininfo()
        assert bci["blocks"] == 100
        # you can use the testcoin_faucet:
        random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
        my_bitcoind.testcoin_faucet(random_address, amount=25)
    finally:
        my_bitcoind.stop_node()
        logger.info("Bitcoind for test_node_running_bitcoin stopped")


def test_fetch_wallet_addresses_for_mining(caplog, wallets_filled_data_folder):
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    # Todo: instantiate a specter-testwallet
    addresses = fetch_wallet_addresses_for_mining("bitcoin", wallets_filled_data_folder)
    assert addresses  # make more sense out of this test


@pytest.mark.slow
@pytest.mark.skip("interferes with conftest fixtures")
def test_node_running_elements(caplog, docker, request):
    # TODO: Refactor this to use conftest.instantiate_bitcoind_controller
    # to reduce redundant code?
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG, logger="cryptoadvance.specter")
    requested_version = request.config.getoption("--elementsd-version")
    try:
        if docker:
            # The NodeController is not available on docker
            return
        else:
            try:
                my_elementsd = ElementsPlainController(
                    elementsd_path=find_node_executable(node_impl="elements"),
                    rpcport=18123,  # Non-standardport to not interfer
                )
            except Exception as e:
                if "Couldn't find executable elementsd" in str(e):
                    pytest.skip(str(e))
                else:
                    raise e

        rpcconn = my_elementsd.start_node(cleanup_at_exit=True, cleanup_hard=True)
        requested_version = request.config.getoption("--elementsd-version")
        assert my_elementsd.version() == requested_version
        assert rpcconn.get_rpc() != None
        assert rpcconn.get_rpc().ipaddress != None
        bci = rpcconn.get_rpc().getblockchaininfo()
        # assert bci["blocks"] == 100
        # you can use the testcoin_faucet:
        prepare_elements_default_wallet(my_elementsd)
        random_address = "el1qqf6tv4n8qp55qc04v4xts5snd9v5uurkry4vskef6lmecahj6c42jt9lnj0432287rs67z9vzq2zvuer036s5mahptwxgyd8k"
        my_elementsd.testcoin_faucet(random_address, amount=25)
    finally:
        my_elementsd.stop_node()
