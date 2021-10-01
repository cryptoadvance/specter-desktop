from enum import auto
import tempfile
import time
import tarfile
import os

import pytest
from cryptoadvance.specter.managers.node_manager import NodeManager
from cryptoadvance.specter.process_controller.bitcoind_controller import (
    BitcoindPlainController,
)
from cryptoadvance.specter.process_controller.elementsd_controller import (
    ElementsPlainController,
)


@pytest.mark.elm
def test_NodeManager(
    bitcoin_regtest: BitcoindPlainController, elements_elreg: ElementsPlainController
):
    with tempfile.TemporaryDirectory("_some_datafolder_tmp") as data_folder:
        print(f"data_folder={data_folder}")
        nm = NodeManager(data_folder=data_folder)
        nm.add_node(
            "bitcoin_regtest",
            False,
            "",
            bitcoin_regtest.rpcconn.rpcuser,
            bitcoin_regtest.rpcconn.rpcpassword,
            bitcoin_regtest.rpcconn.rpcport,
            bitcoin_regtest.rpcconn._ipaddress,
            "http",
            external_node=True,
        )
        assert nm.nodes_names == ["Bitcoin Core", "bitcoin_regtest"]
        nm.switch_node("bitcoin_regtest")
        assert nm.active_node.get_rpc().getblockchaininfo()["chain"] == "regtest"
        nm.add_node(
            "elements_elreg",
            False,
            "",
            elements_elreg.rpcconn.rpcuser,
            elements_elreg.rpcconn.rpcpassword,
            elements_elreg.rpcconn.rpcport,
            elements_elreg.rpcconn._ipaddress,
            "http",
            external_node=True,
        )
        assert nm.nodes_names == ["Bitcoin Core", "bitcoin_regtest", "elements_elreg"]
        nm.switch_node("elements_elreg")
        assert nm.active_node.get_rpc().getblockchaininfo()["chain"] == "elreg"
        time.sleep(20)


""" For some reason this breaks other tests"""


@pytest.mark.skip()
def test_NodeManager_import(bitcoind_path):
    with tempfile.TemporaryDirectory("_some_datafolder_tmp") as data_folder:
        print(f"data_folder={data_folder}")
        nm = NodeManager(data_folder=data_folder, bitcoind_path=bitcoind_path)
        print(os.getcwd())
        # This .bitcoin folder doesn't have a config-file
        btc_tar = tarfile.open(
            "./tests/helpers_testdata/bitcoin_minimum_mainnet_datadir.tgz", "r:gz"
        )
        btc_tar.extractall(os.path.join(data_folder, "somename", ".bitcoin-main"))
        #         # ... so let's create one
        #         with open(
        #             os.path.join(data_folder,"somename",".bitcoin-main","bitcoin.conf"),
        #             "w+",
        #         ) as file:
        #             file.write('''
        # rpcauth=bitcoin:044931c1d498b7c27080d8b981331a65$6ee7929513401c39ca1f7e376e55553c52dcb36a14e8410ac5f514fbf18bedbb
        # server=1
        # listen=1
        # proxy=127.0.0.1:9050
        # bind=127.0.0.1
        # torcontrol=127.0.0.1:9051
        # torpassword=gVzREfuHso6U2OfRRvqT3w
        # fallbackfee=0.0002
        # prune=1000
        #             '''
        #             )

        node = nm.add_internal_node("somename", port=8339)
        try:
            node.start()
            time.sleep(5)
            # assert node.get_rpc().password == None
            nm.switch_node("somename")
            time.sleep(5)
            assert nm.active_node.get_rpc().getblockchaininfo()["chain"] == "main"
        finally:
            node.stop()
