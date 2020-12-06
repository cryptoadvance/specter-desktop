import logging

from cryptoadvance.specter.cli import bitcoind
from click.testing import CliRunner
import sys
import traceback
import mock
from mock import patch, MagicMock, call


def test_bitcoind(caplog):
    # caplog.set_level(logging.DEBUG)

    runner = CliRunner()
    result = runner.invoke(bitcoind, ["--no-mining", "--nodocker", "--cleanuphard"])
    print(result.output)
    if result.exception != None:
        # Makes searching for issues much more convenient
        traceback.print_tb(result.exception.__traceback__)
        print(result.exception, file=sys.stderr)
    assert result.exit_code == 0
    assert (
        "bitcoin-cli: bitcoin-cli -regtest -rpcuser=bitcoin -rpcpassword=secret getblockchaininfo"
        in result.output
    )
    # This might take a lot of time because we're waiting on the bitcoind to terminate
