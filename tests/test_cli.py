import logging

from cryptoadvance.specter.cli import server
from click.testing import CliRunner
import traceback
import mock
from mock import patch

@patch('cryptoadvance.specter.cli.create_app')
@patch('cryptoadvance.specter.cli.init_app')
def test_server_debug(init_app,create_app,caplog):
    caplog.set_level(logging.DEBUG)
    runner = CliRunner()
    result = runner.invoke(server,["--debug"])
    print(result.output)
    if result.exception != None:
        # Makes searching for issues much more convenient
        traceback.print_tb(result.exception.__traceback__)
    print(result.exception)
    assert result.exit_code == 0
    assert "Logging is hopefully configured" in caplog.text
    assert "We're now on level DEBUG on logger cryptoadvance" in caplog.text
