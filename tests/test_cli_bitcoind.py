import logging
import mock
import pytest
import sys
import traceback

from cryptoadvance.specter.cli import bitcoind, elementsd
from click.testing import CliRunner
from mock import patch, MagicMock, call


def test_bitcoind(caplog):
    caplog.set_level(logging.DEBUG)

    runner = CliRunner()
    result = runner.invoke(bitcoind, ["--no-mining", "--nodocker", "--cleanuphard"])
    print(result.output)
    if result.exception != None:
        # Makes searching for issues much more convenient
        traceback.print_tb(result.exception.__traceback__)
        print(result.exception, file=sys.stderr)
    assert result.exit_code == 0
    assert (
        "bitcoin-cli: bitcoin-cli -regtest -rpcport=18443 -rpcuser=bitcoin -rpcpassword=secret getblockchaininfo"
        in result.output
    )
    # This might take a lot of time because we're waiting on the bitcoind to terminate


def test_elements(caplog):
    caplog.set_level(logging.DEBUG)

    runner = CliRunner()
    result = runner.invoke(elementsd, ["--no-mining", "--cleanuphard"])
    print(result.output)
    if result.exception != None:
        if "Couldn't find executable elementsd" in str(result.exception):
            pytest.skip(str(result.exception))

        # Makes searching for issues much more convenient
        traceback.print_tb(result.exception.__traceback__)
        print(result.exception, file=sys.stderr)
    assert result.exit_code == 0
    assert (
        "elements-cli: elements-cli -regtest -rpcport=18884 -rpcuser=liquid -rpcpassword=secret getblockchaininfo"
        in result.output
    )
    # This might take a lot of time because we're waiting on the bitcoind to terminate
