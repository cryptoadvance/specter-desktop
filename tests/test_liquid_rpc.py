from cryptoadvance.specter.liquid.rpc import LiquidRPC


def test_LiquidRpc(elements_elreg):
    rpc = elements_elreg.get_rpc()
    default_rpc = rpc.wallet("")
    assert default_rpc.getbalance() == 20
