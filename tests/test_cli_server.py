import json
import logging
import os
import subprocess
import sys
import traceback
from pathlib import Path

import pytest
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
    create_app.return_value = configured_mock_app()
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


def configured_mock_app(host="127.0.0.1", auth_method="none"):
    mock_app = MagicMock()
    config = dict(mock_config_dict, HOST=host, PORT=123, CERT=None, KEY=None)
    mock_app.config.__getitem__.side_effect = config.__getitem__
    mock_app.specter.config = {"auth": {"method": auth_method}, "tor_status": False}
    return mock_app


def test_docker_entrypoint_uses_configured_host():
    dockerfile = Path(__file__).parent.parent / "Dockerfile"
    entrypoint_line = next(
        line
        for line in dockerfile.read_text().splitlines()
        if line.startswith("ENTRYPOINT")
    )
    entrypoint = json.loads(entrypoint_line.removeprefix("ENTRYPOINT "))

    assert entrypoint == [
        "/usr/local/bin/python3",
        "-m",
        "cryptoadvance.specter",
        "server",
    ]


def test_host_environment_configures_production_host():
    env = os.environ.copy()
    env["HOST"] = "0.0.0.0"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from cryptoadvance.specter.config import ProductionConfig; "
            "print(ProductionConfig.HOST)",
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.stdout.strip() == "0.0.0.0"


@patch("cryptoadvance.specter.cli.cli_server.create_app")
@patch("cryptoadvance.specter.cli.cli_server.init_app")
def test_server_inherits_configured_host(init_app, create_app):
    create_app.return_value = configured_mock_app(host="192.168.1.10")

    result = CliRunner().invoke(server, ["--no-filelog"])

    assert result.exit_code == 0
    create_app.return_value.run.assert_called_once_with(
        debug="WURSTBROT",
        host="192.168.1.10",
        port=123,
        extra_files=["templates"],
    )


@patch("cryptoadvance.specter.cli.cli_server.create_app")
@patch("cryptoadvance.specter.cli.cli_server.init_app")
def test_explicit_host_overrides_configured_host(init_app, create_app):
    create_app.return_value = configured_mock_app(host="192.168.1.10")

    result = CliRunner().invoke(server, ["--host", "127.0.0.2", "--no-filelog"])

    assert result.exit_code == 0
    create_app.return_value.config.__setitem__.assert_called_once_with(
        "HOST", "127.0.0.2"
    )
    assert create_app.return_value.run.call_args.kwargs["host"] == "127.0.0.2"


@patch("cryptoadvance.specter.cli.cli_server.create_app")
def test_invalid_configured_host_fails_with_clear_error(create_app):
    create_app.return_value = configured_mock_app(host="")

    result = CliRunner().invoke(server, ["--no-filelog"])

    assert result.exit_code != 0
    assert "Configured HOST must be a non-empty hostname or IP address" in result.output
    create_app.return_value.run.assert_not_called()


@patch("cryptoadvance.specter.cli.cli_server.create_app")
@patch("cryptoadvance.specter.cli.cli_server.init_app")
@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "localhost", "::1"])
def test_unauthenticated_loopback_host_does_not_warn(
    init_app, create_app, caplog, host
):
    create_app.return_value = configured_mock_app(host=host)

    result = CliRunner().invoke(server, ["--no-filelog"])

    assert result.exit_code == 0
    assert "authentication disabled" not in caplog.text


@patch("cryptoadvance.specter.cli.cli_server.create_app")
@patch("cryptoadvance.specter.cli.cli_server.init_app")
def test_unauthenticated_external_host_warns(init_app, create_app, caplog):
    create_app.return_value = configured_mock_app(host="0.0.0.0")
    caplog.set_level(logging.WARNING)

    result = CliRunner().invoke(server, ["--no-filelog"])

    assert result.exit_code == 0
    assert "non-loopback host 0.0.0.0 with authentication disabled" in caplog.text
    assert "Anyone who can reach port 123" in caplog.text


@patch("cryptoadvance.specter.cli.cli_server.create_app")
@patch("cryptoadvance.specter.cli.cli_server.init_app")
def test_authenticated_external_host_does_not_warn(init_app, create_app, caplog):
    create_app.return_value = configured_mock_app(
        host="0.0.0.0", auth_method="usernamepassword"
    )

    result = CliRunner().invoke(server, ["--no-filelog"])

    assert result.exit_code == 0
    assert "authentication disabled" not in caplog.text


@patch("cryptoadvance.specter.cli.cli_server.create_app")
@patch("cryptoadvance.specter.cli.cli_server.init_app")
def test_external_hwibridge_does_not_warn(init_app, create_app, caplog):
    create_app.return_value = configured_mock_app(host="0.0.0.0")

    result = CliRunner().invoke(server, ["--hwibridge", "--no-filelog"])

    assert result.exit_code == 0
    assert "authentication disabled" not in caplog.text
