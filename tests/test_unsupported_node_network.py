import pytest
from embit.liquid.networks import get_network

from cryptoadvance.specter.node import AbstractNode, Node
from cryptoadvance.specter.specter_error import SpecterError


def _node(chain, params):
    node = object.__new__(Node)
    node._info = {"chain": chain}
    node._network_info = {"version": 300000}
    node._network_parameters = params
    return node


def test_unsupported_running_node_does_not_offer_mainnet_derivation():
    node = _node("testnet4", None)
    with pytest.raises(SpecterError, match="testnet4"):
        _ = node.network_parameters
    with pytest.raises(SpecterError, match="testnet4"):
        AbstractNode.network_parameters.fget(node)
    # Node info may still display the actual chain without network parameters.
    assert node.chain == "testnet4"


def test_supported_node_keeps_its_network_parameters():
    node = _node("test", get_network("test"))
    assert node.network_parameters["bech32"] == "tb"
    assert AbstractNode.network_parameters.fget(node)["bech32"] == "tb"
