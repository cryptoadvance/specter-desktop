import pytest

from rpc import BitcoinCLI

def test_BitcoinCli(bitcoin_regtest):
    brt = bitcoin_regtest # stupid long name
    cli = BitcoinCLI(brt.rpcuser, brt.rpcpassword, host=brt.ipaddress, port=brt.rpcport)
    cli.getblockchaininfo()
    # To investigate the Bitcoin API, this is a great resource:
    # https://chainquery.com/bitcoin-cli
