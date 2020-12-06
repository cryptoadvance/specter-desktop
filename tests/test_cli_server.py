import logging

from cryptoadvance.specter.cli import server
from click.testing import CliRunner
import sys
import traceback
import mock
from mock import patch, MagicMock, call


@patch("cryptoadvance.specter.cli.cli_server.create_app")
@patch("cryptoadvance.specter.cli.cli_server.init_app")
def test_server_host_and_port(init_app, create_app, caplog):
    caplog.set_level(logging.DEBUG)
    mock_app = MagicMock()
    mock_app.config = MagicMock()
    d = {
        "SPECTER_DATA_FOLDER": "someValueWillGetChanged",
        "PORT": "123",
        "DEBUG": "WURSTBROT",
    }
    mock_app.config.__getitem__.side_effect = d.__getitem__
    create_app.return_value = mock_app
    runner = CliRunner()
    result = runner.invoke(server, ["--port", "456", "--host", "0.0.0.1"])
    print(result.output)
    if result.exception != None:
        # Makes searching for issues much more convenient
        traceback.print_tb(result.exception.__traceback__)
        print(result.exception, file=sys.stderr)
    print(mock_app.config.mock_calls)
    assert result.exit_code == 0
    mock_app.config.__setitem__.assert_called_with("PORT", 456)
    mock_app.run.assert_called_with(
        debug="WURSTBROT", host="0.0.0.1", port="123", extra_files=["templates"]
    )


@patch("cryptoadvance.specter.cli.cli_server.create_app")
@patch("cryptoadvance.specter.cli.cli_server.init_app")
def test_server_host_and_port(init_app, create_app, caplog):
    caplog.set_level(logging.DEBUG)
    mock_app = MagicMock()
    mock_app.config = MagicMock()
    d = {
        "PORT": "123",
        "DEBUG": "WURSTBROT",
        # We don't want to make a more sophisticated mock, so we simply set here
        # the same value we set via CMD-Line
        "CERT": "bla",
        "KEY": "blub",
    }
    mock_app.config.__getitem__.side_effect = d.__getitem__
    create_app.return_value = mock_app
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(server, ["--cert", "bla", "--key", "blub"])
    print(result.output)
    if result.exception != None:
        # Makes searching for issues much more convenient
        traceback.print_tb(result.exception.__traceback__)
        print(result.exception, file=sys.stderr)
    assert result.exit_code == 0
    print(mock_app.config.mock_calls)
    mock_app.config.__setitem__.call_count = 2
    mock_app.config.__setitem__.assert_called_with("KEY", "blub")
    mock_app.config.__setitem__.assert_any_call("CERT", "bla")
    # This doesn't work as the tmp-directory is always different
    # mock_app.run.assert_called_with(debug='WURSTBROT', host='0.0.0.1', port='123', extra_files=['templates'],ssl_context=('/tmp/tmpb_2552yg/bla', '/tmp/tmpb_2552yg/blub')))
    # So let's check differently:

    print(mock_app.run.call_args.kwargs)
    # results in something like:
    # {'debug': 'WURSTBROT', 'host': '127.0.0.1', 'port': '123', 'extra_files': ['templates'], 'ssl_context': ('/tmp/tmpnzivft_y/bla', '/tmp/tmpnzivft_y/blub')}
    assert mock_app.run.call_args.kwargs["ssl_context"][0].endswith("/bla")
    assert mock_app.run.call_args.kwargs["ssl_context"][1].endswith("/blub")


@patch("cryptoadvance.specter.cli.cli_server.create_app")
@patch("cryptoadvance.specter.cli.cli_server.init_app")
def test_server_debug(init_app, create_app, caplog):
    caplog.set_level(logging.DEBUG)
    runner = CliRunner()
    result = runner.invoke(server, ["--debug"])
    print(result.output)
    if result.exception != None:
        # Makes searching for issues much more convenient
        traceback.print_tb(result.exception.__traceback__)
    print(result.exception)
    assert result.exit_code == 0
    assert "Logging is hopefully configured" in caplog.text
    assert "We're now on level DEBUG on logger cryptoadvance" in caplog.text


@patch("cryptoadvance.specter.cli.cli_server.create_app")
@patch("cryptoadvance.specter.cli.cli_server.init_app")
def test_server_datafolder(init_app, create_app, caplog):
    caplog.set_level(logging.DEBUG)
    mock_app = MagicMock()
    mock_app.config = MagicMock()
    d = {
        "SPECTER_DATA_FOLDER": "someValueWillGetChanged",
        "PORT": "123",
        "DEBUG": "WURSTBROT",
    }
    mock_app.config.__getitem__.side_effect = d.__getitem__
    create_app.return_value = mock_app
    runner = CliRunner()
    result = runner.invoke(server, ["--specter-data-folder", "~/.specter-some-folder"])
    print(result.output)
    if result.exception != None:
        # Makes searching for issues much more convenient
        traceback.print_tb(result.exception.__traceback__)
        print(result.exception, file=sys.stderr)
    print(mock_app.config.mock_calls)
    assert result.exit_code == 0
    mock_app.config.__setitem__.assert_called_once_with(
        "SPECTER_DATA_FOLDER", "~/.specter-some-folder"
    )


@patch("cryptoadvance.specter.cli.cli_server.create_app")
@patch("cryptoadvance.specter.cli.cli_server.init_app")
def test_server_config(init_app, create_app, caplog):
    caplog.set_level(logging.DEBUG)
    mock_app = MagicMock()
    mock_app.config = MagicMock()
    d = {
        "PORT": "123",
        "DEBUG": "WURSTBROT",
        # We don't want to make a more sophisticated mock, so we simply set here
        # the same value we set via CMD-Line
        "CERT": "bla",
        "KEY": "blub",
    }
    mock_app.config.__getitem__.side_effect = d.__getitem__
    create_app.return_value = mock_app
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(server, ["--config", "MuhConfig"])
    print(result.output)
    if result.exception != None:
        # Makes searching for issues much more convenient
        traceback.print_tb(result.exception.__traceback__)
        print(result.exception, file=sys.stderr)
    assert result.exit_code == 0
    print(mock_app.config.mock_calls)
    create_app.assert_called_once_with(config="cryptoadvance.specter.config.MuhConfig")
