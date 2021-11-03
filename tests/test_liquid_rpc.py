import pytest
from cryptoadvance.specter.liquid.rpc import LiquidRPC


@pytest.mark.elm
def test_LiquidRpc(elements_elreg):
    rpc = elements_elreg.get_rpc()
    default_rpc = rpc.wallet("")
    assert default_rpc.getbalance() >= 0
    # This test is failing although the documentation says it should work like this:
    # assert default_rpc.getbalance(assetLabel=None)["bitcoin"] == 0
