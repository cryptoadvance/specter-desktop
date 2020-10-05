import pytest

from cryptoadvance.specter.rpc import BitcoinRPC, RpcError


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
