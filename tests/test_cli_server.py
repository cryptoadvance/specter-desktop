import logging
import os
import sys
import traceback

from click.testing import CliRunner
from cryptoadvance.specter.cli import server
from mock import MagicMock, call, patch

mock_config_dict = {
    "HOST": "127.0.0.1",
    "PORT": "123",
    "DEBUG": "WURSTBROT",
    "SPECTER_SSL_CERT_SUBJECT_C": "AT",
    "SPECTER_SSL_CERT_SUBJECT_ST": "Blub",
    "SPECTER_SSL_CERT_SUBJECT_L": "Blub",
    "SPECTER_SSL_CERT_SUBJECT_O": "Blub",
    "SPECTER_SSL_CERT_SUBJECT_OU": "Blub",
    "SPECTER_SSL_CERT_SUBJECT_CN": "Blub",
    "SPECTER_SSL_CERT_SERIAL_NUMBER": 123,
    # We don't want to make a more sophisticated mock, so we simply set here
    # the same value we set via CMD-Line
    "CERT": "bla",
    "KEY": "blub",
}


@patch("cryptoadvance.specter.cli.cli_server.create_app")
@patch("cryptoadvance.specter.cli.cli_server.init_app")
def test_server_host_and_port(init_app, create_app, caplog):
    """This test will fail if you have turned on live-logging in pyproject.toml (log_cli = 1 )"""
    caplog.set_level(logging.DEBUG)
    mock_app = MagicMock()
    mock_app.config = MagicMock()
    d = mock_config_dict
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
    """This test will fail if you have turned on live-logging in pyproject.toml (log_cli = 1 )"""
    caplog.set_level(logging.DEBUG)
    mock_app = MagicMock()
    mock_app.config = MagicMock()
    d = mock_config_dict
    mock_app.config.__getitem__.side_effect = d.__getitem__
    create_app.return_value = mock_app
    runner = CliRunner()
    try:
        with runner.isolated_filesystem():
            result = runner.invoke(
                server, ["--cert", "bla", "--key", "blub", "--no-filelog"]
            )
    finally:
        # not sure why i need to do that in an isolated_filesystem ?!
        tidy_up()
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
    assert mock_app.run.call_args.kwargs["ssl_context"][0].endswith("bla")
    assert mock_app.run.call_args.kwargs["ssl_context"][1].endswith("blub")


@patch("cryptoadvance.specter.cli.cli_server.create_app")
@patch("cryptoadvance.specter.cli.cli_server.init_app")
def test_server_debug(init_app, create_app, caplog):
    """This test will fail if you have turned on live-logging in pyproject.toml (log_cli = 1 )"""
    caplog.set_level(logging.DEBUG)
    runner = CliRunner()
    result = runner.invoke(server, ["--debug", "--no-filelog"])
    print(result.output)
    if result.exception != None:
        # Makes searching for issues much more convenient
        traceback.print_tb(result.exception.__traceback__)
    print(result.exception)
    assert result.exit_code == 0
    assert "We're now on level DEBUG on logger cryptoadvance" in caplog.text


@patch("cryptoadvance.specter.cli.cli_server.create_app")
@patch("cryptoadvance.specter.cli.cli_server.init_app")
def test_server_datafolder(init_app, create_app, caplog):
    """This test will fail if you have turned on live-logging in pyproject.toml (log_cli = 1 )"""
    caplog.set_level(logging.DEBUG)
    mock_app = MagicMock()
    mock_app.config = MagicMock()
    d = mock_config_dict
    mock_app.config.__getitem__.side_effect = d.__getitem__
    create_app.return_value = mock_app
    runner = CliRunner()
    result = runner.invoke(
        server, ["--specter-data-folder", "~/.specter-some-folder", "--no-filelog"]
    )
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
    """This test will fail if you have turned on live-logging in pyproject.toml (log_cli = 1 )"""
    caplog.set_level(logging.DEBUG)
    mock_app = MagicMock()
    mock_app.config = MagicMock()
    d = {
        "HOST": "127.0.0.1",
        "PORT": "123",
        "DEBUG": "WURSTBROT",
        "SPECTER_SSL_CERT_SUBJECT_C": "AT",
        "SPECTER_SSL_CERT_SUBJECT_ST": "Blub",
        "SPECTER_SSL_CERT_SUBJECT_L": "Blub",
        "SPECTER_SSL_CERT_SUBJECT_O": "Blub",
        "SPECTER_SSL_CERT_SUBJECT_OU": "Blub",
        "SPECTER_SSL_CERT_SUBJECT_CN": "Blub",
        "SPECTER_SSL_CERT_SERIAL_NUMBER": 123,
        # We don't want to make a more sophisticated mock, so we simply set here
        # the same value we set via CMD-Line
        "CERT": "bla",
        "KEY": "blub",
    }
    mock_app.config.__getitem__.side_effect = d.__getitem__
    create_app.return_value = mock_app
    runner = CliRunner()
    try:
        with runner.isolated_filesystem():
            result = runner.invoke(server, ["--config", "MuhConfig", "--no-filelog"])
    finally:
        # not sure why i need to do that in an isolated_filesystem ?!
        tidy_up()
    print(result.output)
    if result.exception != None:
        # Makes searching for issues much more convenient
        traceback.print_tb(result.exception.__traceback__)
        print(result.exception, file=sys.stderr)
    assert result.exit_code == 0
    print(mock_app.config.mock_calls)
    create_app.assert_called_once_with(config="cryptoadvance.specter.config.MuhConfig")
    tidy_up()


def tidy_up():
    if os.path.exists("bla"):
        os.remove("bla")
    if os.path.exists("blub"):
        os.remove("blub")
