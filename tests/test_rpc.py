import pytest

from cryptoadvance.specter.rpc import BitcoinRPC, RpcError
from cryptoadvance.specter.specter_error import SpecterError


def test_BitcoinRpc(bitcoin_regtest):
    brt = bitcoin_regtest  # stupid long name
    rpc = BitcoinRPC(
        brt.rpcconn.rpcuser,
        brt.rpcconn.rpcpassword,
        host=brt.rpcconn.ipaddress,
        port=brt.rpcconn.rpcport,
    )
    rpc.getblockchaininfo()
    # To investigate the Bitcoin API, here are some great resources:
    # https://bitcoin.org/en/developer-reference#bitcoin-core-apis
    # https://chainquery.com/bitcoin-cli
    # https://github.com/ChristopherA/Learning-Bitcoin-from-the-Command-Line

    # Errorhandling:
    try:
        rpc.getSomethingNonExisting()
    except RpcError as rpce:
        assert rpce.error_code == -32601
        assert rpce.error_msg == "Method not found"


def test_BitcoinRpc_timeout(bitcoin_regtest, caplog):
    try:
        brt = bitcoin_regtest  # stupid long name
        BitcoinRPC.default_timeout = 0.001
        rpc = BitcoinRPC(
            brt.rpcconn.rpcuser,
            brt.rpcconn.rpcpassword,
            host=brt.rpcconn.ipaddress,
            port=brt.rpcconn.rpcport,
        )

        with pytest.raises(SpecterError) as se:
            rpc.createwallet("some_test_wallet_name_392")
        assert "Timeout after 0.001" in str(se.value)
        assert (
            "while BitcoinRPC call(                            ) payload:[{'method': 'createwallet', 'params': ['some_test_wallet_name_392'], 'jsonrpc': '2.0', 'id': 0}]"
            in caplog.text
        )

        rpc.timeout = 0.0001
        with pytest.raises(SpecterError) as se:
            rpc.createwallet("some_test_wallet_name_393")
        assert "Timeout after 0.0001" in str(se.value)
        assert "Timeout after 0.001" in caplog.text
    finally:
        BitcoinRPC.default_timeout = None
