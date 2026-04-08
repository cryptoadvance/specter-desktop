import json
import logging
import pytest
import requests
from requests import Response
from unittest.mock import MagicMock
from cryptoadvance.specter.rpc import (
    BitcoinRPC,
    RpcError,
    _detect_rpc_confs_via_datadir,
    get_rpcconfig,
    get_walletdir,
)
from cryptoadvance.specter.specter_error import SpecterError

# To investigate the Bitcoin API, here are some great resources:
# https://bitcoin.org/en/developer-reference#bitcoin-core-apis
# https://chainquery.com/bitcoin-cli
# https://github.com/ChristopherA/Learning-Bitcoin-from-the-Command-Line


class CustomResponse(Response):
    """We need to fake the Response if we have to handle errors. As a Response object is not able
    to be initialized directly, we're subclassing here and create the necessary constructor
    """

    def __init__(self, status_code, json, headers):
        self.status_code = status_code
        self._content = json
        self.headers = headers
        self.encoding = None


def test_get_rpcconfig0(empty_data_folder):
    c = get_rpcconfig(empty_data_folder)
    assert c["bitcoin.conf"]["default"] == {}
    assert c["bitcoin.conf"]["main"] == {}
    assert c["bitcoin.conf"]["regtest"] == {}
    assert c["bitcoin.conf"]["test"] == {}


def test_get_rpcconfig1():
    c = get_rpcconfig("./tests/misc_testdata/rpc_autodetection/example1")
    # Looks like this:
    # regtest=1
    # rpcconnect=bitcoin
    # main.rpcport=8332
    # test.rpcport=18332
    # regtest.rpcport=18443
    # rpcuser=bitcoin
    # rpcpassword=CHANGEME
    assert c["bitcoin.conf"] == {
        "default": {
            "regtest": "1",
            "rpcconnect": "bitcoin",
            "rpcpassword": "CHANGEME",
            "rpcuser": "bitcoin",
        },
        "main": {"rpcport": "8332"},
        "regtest": {"rpcport": "18443"},
        "test": {"rpcport": "18332"},
        "signet": {},
    }


def test_get_rpcconfig2(empty_data_folder):
    c = get_rpcconfig("./tests/misc_testdata/rpc_autodetection/example2")
    # maxmempool=700
    # server=1
    # prune=700
    # [main]
    # [test]
    # [regtest]
    # prune=0
    # zmqpubrawblock=tcp://127.0.0.1:29000
    # zmqpubrawtx=tcp://127.0.0.1:29000
    # zmqpubhashtx=tcp://127.0.0.1:29000
    # zmqpubhashblock=tcp://127.0.0.1:29000
    assert c["bitcoin.conf"] == {
        "default": {
            "maxmempool": "700",
            "server": "1",
            "prune": "700",
        },
        "main": {},
        "regtest": {
            "prune": "0",
            "zmqpubrawblock": "tcp://127.0.0.1:29000",
            "zmqpubrawtx": "tcp://127.0.0.1:29000",
            "zmqpubhashtx": "tcp://127.0.0.1:29000",
            "zmqpubhashblock": "tcp://127.0.0.1:29000",
        },
        "test": {},
        "signet": {},
    }


def test_get_walletdir_not_configured(empty_data_folder):
    """get_walletdir returns None when walletdir is not set in bitcoin.conf."""
    assert get_walletdir(empty_data_folder, "main") is None
    assert get_walletdir(empty_data_folder, "regtest") is None


def test_get_walletdir_default_section():
    """get_walletdir returns the walletdir from the [default] section."""
    datadir = "./tests/misc_testdata/rpc_autodetection/example_walletdir_default"
    assert get_walletdir(datadir, "main") == "/custom/wallets"
    assert get_walletdir(datadir, "regtest") == "/custom/wallets"
    assert get_walletdir(datadir, "test") == "/custom/wallets"


def test_get_walletdir_network_section_takes_precedence():
    """Network-specific walletdir takes precedence over the [default] walletdir."""
    datadir = "./tests/misc_testdata/rpc_autodetection/example_walletdir_network"
    # regtest section overrides the default
    assert get_walletdir(datadir, "regtest") == "/regtest/wallets"
    # other chains fall back to default
    assert get_walletdir(datadir, "main") == "/default/wallets"
    assert get_walletdir(datadir, "test") == "/default/wallets"


def test_get_walletdir_dot_notation_network_override(tmp_path):
    """Dot-notation network walletdir overrides the default walletdir."""
    bitcoin_conf = tmp_path / "bitcoin.conf"
    bitcoin_conf.write_text(
        "walletdir=/default/wallets\n" "regtest.walletdir=/regtest/wallets\n"
    )
    assert get_walletdir(str(tmp_path), "regtest") == "/regtest/wallets"
    assert get_walletdir(str(tmp_path), "main") == "/default/wallets"
    assert get_walletdir(str(tmp_path), "test") == "/default/wallets"


def test_get_walletdir_expands_tilde(tmp_path, monkeypatch):
    """get_walletdir expands ~ in the datadir path so user-entered paths work."""
    monkeypatch.setenv("HOME", str(tmp_path))
    bitcoin_conf = tmp_path / "bitcoin.conf"
    bitcoin_conf.write_text("walletdir=/custom/wallets\n")
    assert get_walletdir("~", "main") == "/custom/wallets"


def test_detect_rpc_confs_via_datadir1():
    c = _detect_rpc_confs_via_datadir(
        datadir="./tests/misc_testdata/rpc_autodetection/example1"
    )
    # Looks like this:
    # regtest=1
    # rpcconnect=bitcoin
    # main.rpcport=8332
    # test.rpcport=18332
    # regtest.rpcport=18443
    # rpcuser=bitcoin
    # rpcpassword=CHANGEME
    assert c == [
        {"host": "bitcoin", "password": "CHANGEME", "port": 18443, "user": "bitcoin"}
    ]


def test_detect_rpc_confs_via_datadir2(caplog, empty_data_folder):
    caplog.set_level(logging.DEBUG)
    c = _detect_rpc_confs_via_datadir(
        datadir="./tests/misc_testdata/rpc_autodetection/example2"
    )
    # maxmempool=700
    # server=1
    # prune=700
    # [main]
    # [test]
    # [regtest]
    # prune=0
    # zmqpubrawblock=tcp://127.0.0.1:29000
    # zmqpubrawtx=tcp://127.0.0.1:29000
    # zmqpubhashtx=tcp://127.0.0.1:29000
    # zmqpubhashblock=tcp://127.0.0.1:29000
    assert c == []


def test_RpcError_response(caplog):
    caplog.set_level(logging.DEBUG)
    # Creating an RpcError with a Response object

    # Faking a response which looks like a Wallet has not been found
    response = requests.post(
        "https://httpbin.org/anything",
        headers={"accept": "application/json"},
        json={
            "error": {
                "message": "Requested wallet does not exist or is not loaded",
                "code": -32601,
            }
        },
    )
    response.status_code = 500
    response._content = json.dumps(
        {
            "error": {
                "message": "Requested wallet does not exist or is not loaded",
                "code": -32601,
            }
        }
    ).encode("ascii")
    assert response.status_code == 500
    assert response.json()["error"]["message"]
    rpce = RpcError("some Message", response)

    assert rpce.status_code == 500
    assert rpce.error_msg == "Requested wallet does not exist or is not loaded"
    assert rpce.error_code == -32601


def test_RpcError_response_incomplete(caplog):
    # Creating an RpcError with a Response object
    try:
        # Faking a response which looks like a Wallet has not been found
        response = requests.post(
            "https://httpbin.org/anything",
            headers={"accept": "application/json"},
            json={},
        )
        response.status_code = 500
        raise RpcError("some Message", response)
    except RpcError as rpce:
        assert rpce.status_code == 500
        assert rpce.error_code == -99
        assert rpce.error_msg.startswith("some Message")


def test_RpcError_via_params():
    # Via status_code, error_code and error_msg
    try:
        raise RpcError(
            "some Message",
            status_code=500,
            error_code=-32601,
            error_msg="Requested wallet does not exist or is not loaded",
        )
    except RpcError as rpce:
        assert rpce.status_code == 500
        assert rpce.error_code == -32601
        assert rpce.error_msg == "Requested wallet does not exist or is not loaded"

    # Only message
    try:
        raise RpcError("some message")
    except RpcError as rpce:
        assert rpce.status_code == 500
        assert rpce.error_code == -99
        assert rpce.error_msg == "some message"

    # omitting error_msg
    try:
        raise RpcError("some message", status_code=500, error_code=-32601)
    except RpcError as rpce:
        assert rpce.status_code == 500
        assert rpce.error_code == -32601
        assert rpce.error_msg == "some message"


def test_BitcoinRpc(rpc):
    result = rpc.getblockchaininfo()
    assert result.get("error") == None
    assert result["blocks"] >= 100


def test_BitcoinRpc_methodNotExisting(rpc):
    # Errorhandling:
    try:
        rpc.getSomethingNonExisting()
    except RpcError as rpce:
        assert rpce.status_code == 500
        assert rpce.error_code == -32601
        assert rpce.error_msg == "Method not found"


def test_BitcoinRpc_walletNotExisting(rpc):
    # Errorhandling:
    rpc = rpc.wallet("SomeWallet")
    rpc.timeout = 0.1
    try:
        rpc.getwalletinfo()
    except RpcError as rpce:
        assert rpce.status_code == 500
        assert rpce.error_code == -18
        assert rpce.error_msg == "Requested wallet does not exist or is not loaded"


def test_BitcoinRpc_timeout(rpc, caplog):
    rpc.timeout = 0.001
    try:
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


def test_BitcoinRpc_malformed_response():
    """Test handling of malformed RPC responses"""
    # Create a mock RPC instance
    rpc = BitcoinRPC("user", "pass", "127.0.0.1", 8332)

    # Test 1: Response is not a dict (e.g., a string)
    rpc.multi = MagicMock(return_value=["not a dict"])
    with pytest.raises(RpcError) as exc_info:
        rpc.getblockchaininfo()
    assert "Invalid response format" in str(exc_info.value)
    assert "expected dict" in str(exc_info.value)
    assert "Invalid response format" in exc_info.value.error_msg

    # Test 2: Response dict has error but error is not a dict
    rpc.multi = MagicMock(return_value=[{"error": "plain string error"}])
    with pytest.raises(RpcError) as exc_info:
        rpc.getblockchaininfo()
    assert "plain string error" in str(exc_info.value)
    # Ensure error_msg doesn't degrade to UNKNOWN API-ERROR
    assert "plain string error" in exc_info.value.error_msg
    assert "UNKNOWN API-ERROR" not in exc_info.value.error_msg

    # Test 3: Response dict has error dict but missing 'message' key
    rpc.multi = MagicMock(return_value=[{"error": {"code": -1}}])
    with pytest.raises(RpcError) as exc_info:
        rpc.getblockchaininfo()
    # Should handle missing message gracefully
    assert "getblockchaininfo" in str(exc_info.value)
    # Ensure error_msg contains the error dict representation, not UNKNOWN API-ERROR
    assert "UNKNOWN API-ERROR" not in exc_info.value.error_msg
    assert exc_info.value.error_code == -1

    # Test 4: Response dict missing both 'error' and 'result' keys
    rpc.multi = MagicMock(return_value=[{}])
    with pytest.raises(RpcError) as exc_info:
        rpc.getblockchaininfo()
    assert "missing 'result' key" in str(exc_info.value)
    assert "missing 'result' key" in exc_info.value.error_msg

    # Test 5: Valid response with error=None should work
    rpc.multi = MagicMock(return_value=[{"error": None, "result": {"blocks": 100}}])
    result = rpc.getblockchaininfo()
    assert result == {"blocks": 100}

    # Test 6: Valid response without error key should work
    rpc.multi = MagicMock(return_value=[{"result": {"blocks": 200}}])
    result = rpc.getblockchaininfo()
    assert result == {"blocks": 200}


@pytest.fixture
def rpc(bitcoin_regtest):
    brt = bitcoin_regtest  # stupid long name
    rpc = BitcoinRPC(
        brt.rpcconn.rpcuser,
        brt.rpcconn.rpcpassword,
        host=brt.rpcconn.ipaddress,
        port=brt.rpcconn.rpcport,
    )
    return rpc
