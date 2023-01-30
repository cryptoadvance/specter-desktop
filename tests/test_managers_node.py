from enum import auto
import tempfile
import time
import tarfile
import os
from unittest.mock import MagicMock

import pytest
from cryptoadvance.specter.managers.node_manager import NodeManager
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.process_controller.bitcoind_controller import (
    BitcoindPlainController,
)
from cryptoadvance.specter.process_controller.elementsd_controller import (
    ElementsPlainController,
)


def test_node_manager_basics(
    empty_data_folder, node, node_with_different_port, specter_regtest_configured
):
    nodes_folder = empty_data_folder + "/nodes"
    nm = specter_regtest_configured.node_manager
    # # Load from disk to get the other two nodes
    assert sorted(list(nm.nodes.keys())) == [
        "bitcoin_core",
        "node_with_a_different_port",
        "standard_node",
    ]
    assert nm.nodes_names == [
        "Standard node",
        "Node with a different port",
        "Bitcoin Core",
    ]
    nm.load_from_disk(nodes_folder)
    assert nm.nodes_names == [
        "Standard node",
        "Node with a different port",
        "Bitcoin Core",
    ]
    # Checking some standard methods and properties
    assert nm.get_by_alias("node_with_a_different_port") == nm.get_by_name(
        "Node with a different port"
    )
    default_node = nm.get_by_alias("bitcoin_core")
    node_with_a_different_port = nm.get_by_alias("node_with_a_different_port")
    assert nm.active_node == default_node
    assert specter_regtest_configured.config["active_node_alias"] == "bitcoin_core"
    # Switching the node via the node manager does not change the active_node_alias in the config, only specter.update_active_node() does
    nm.switch_node("node_with_a_different_port")
    assert nm.active_node == node_with_a_different_port
    assert specter_regtest_configured.config["active_node_alias"] == "bitcoin_core"
    specter_regtest_configured.update_active_node("node_with_a_different_port")
    assert (
        specter_regtest_configured.config["active_node_alias"]
        == "node_with_a_different_port"
    )
    assert nm.active_node == node_with_a_different_port
    # Deleting a node
    nm.delete_node(node_with_a_different_port, specter_regtest_configured)
    assert nm.nodes_names == ["Standard node", "Bitcoin Core"]
    # Check that with the deletion of the active node the switch to the next node work, the first node in the list, here the Standard node, is switched to
    assert specter_regtest_configured.config["active_node_alias"] == "standard_node"
    assert nm._active_node == "standard_node"
    # Check the error handling
    with pytest.raises(
        SpecterError,
        match="Node with a different port not found, node could not be deleted.",
    ):
        nm.delete_node(node_with_a_different_port, specter_regtest_configured)
    with pytest.raises(
        SpecterError, match="Node alias node_with_a_different_port does not exist!"
    ):
        nm.switch_node("node_with_a_different_port")


@pytest.mark.elm
def test_switch_nodes_across_chains(
    bitcoin_regtest: BitcoindPlainController, elements_elreg: ElementsPlainController
):
    with tempfile.TemporaryDirectory(
        prefix="pytest_NodeManager_datafolder"
    ) as data_folder:
        print(f"data_folder={data_folder}")
        nm = NodeManager(data_folder=data_folder)
        nm.add_external_node(
            "BTC",
            "bitcoin_regtest",
            False,
            "",
            bitcoin_regtest.rpcconn.rpcuser,
            bitcoin_regtest.rpcconn.rpcpassword,
            bitcoin_regtest.rpcconn.rpcport,
            bitcoin_regtest.rpcconn._ipaddress,
            "http",
        )
        assert nm.nodes_names == ["bitcoin_regtest"]
        nm.switch_node("bitcoin_regtest")
        assert nm.active_node.rpc.getblockchaininfo()["chain"] == "regtest"
        nm.add_external_node(
            "ELM",
            "elements_elreg",
            False,
            "",
            elements_elreg.rpcconn.rpcuser,
            elements_elreg.rpcconn.rpcpassword,
            elements_elreg.rpcconn.rpcport,
            elements_elreg.rpcconn._ipaddress,
            "http",
        )
        assert nm.nodes_names == ["bitcoin_regtest", "elements_elreg"]
        nm.switch_node("elements_elreg")
        assert nm.active_node.rpc.getblockchaininfo()["chain"] == "elreg"
