from unittest.mock import MagicMock
from cryptoadvance.specterext.spectrum.bridge_rpc import BridgeRPC
from cryptoadvance.spectrum.spectrum import RPCError as SpectrumRpcError
from cryptoadvance.specter.rpc import RpcError as SpecterRpcError
from flask import Flask
import pytest


@pytest.mark.skip()
def test_getmininginfobridge(caplog, app: Flask):
    print(app.spectrum)
    brpc = BridgeRPC(app.spectrum)

    data = brpc.getmininginfo()
    assert data["blocks"] >= 0
    data = brpc.getblockchaininfo()
    assert data["blocks"] >= 0
    data = brpc.getnetworkinfo()
    assert data["version"] == 230000
    data = brpc.getmempoolinfo()
    assert data["mempoolminfee"] == 0.00001000  # bad, needs a fix!
    data = brpc.uptime()
    assert data >= 0  # in seconds and therefore almost zero

    data = brpc.getblockcount()
    assert data >= 0  # hmmm, why is that?
    with app.app_context():
        data = brpc.listwallets()
        assert data == []
        data = brpc.createwallet("some_test_wallet_name_123")
        assert data["name"] == "some_test_wallet_name_123"
        data = brpc.listwallets()
        assert data == ["some_test_wallet_name_123"]

        wbrpc = brpc.wallet("some_test_wallet_name_123")
        assert wbrpc is not None
        data = wbrpc.getwalletinfo()
        print(data)
        assert data["walletname"] == "some_test_wallet_name_123"

    # assert False


def test_exceptionHandling():
    spectrum_mock: MagicMock = MagicMock()
    spectrum_mock.walletcreatefundedpsbt.side_effect = SpectrumRpcError("Muh")

    with pytest.raises(SpectrumRpcError):
        spectrum_mock.walletcreatefundedpsbt("muh", "meh")

    brpc = BridgeRPC(spectrum_mock)
    with pytest.raises(SpecterRpcError):
        brpc.walletcreatefundedpsbt()
