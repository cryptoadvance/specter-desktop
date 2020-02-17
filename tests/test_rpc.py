import pytest

from specter.rpc import BitcoinCLI, RpcError

def test_BitcoinCli(bitcoin_regtest):
    brt = bitcoin_regtest # stupid long name
    cli = BitcoinCLI(brt.rpcconn.rpcuser, brt.rpcconn.rpcpassword, host=brt.rpcconn.ipaddress, port=brt.rpcconn.rpcport)
    cli.getblockchaininfo()
    # To investigate the Bitcoin API, here are some great resources:
    # https://bitcoin.org/en/developer-reference#bitcoin-core-apis
    # https://chainquery.com/bitcoin-cli
    # https://github.com/ChristopherA/Learning-Bitcoin-from-the-Command-Line

    # Errorhandling:
    try:
        cli.getSomethingNonExisting()
    except RpcError as rpce:
        assert rpce.error_code == -32601
        assert rpce.error_msg == "Method not found"

    
    

