from enum import auto
import tempfile

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
