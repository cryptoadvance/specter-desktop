"""Unit tests for the log redaction helpers.

These tests do not need a node: they exercise RPC logs and wallet import errors.
"""

import json
import logging
from unittest.mock import MagicMock

import pytest
import requests

from cryptoadvance.specter.rpc import BitcoinRPC, RpcError
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.util.wallet_importer import WalletImporter
from cryptoadvance.specter.util.redact import (
    REDACTED,
    redact_rpc_payload,
    redact_wallet_document,
    redact_text,
)

XPRV = "xprv9s21ZrQH143K3QTDL4LXw2F7HEK3wJUD2nW2nRk4stbPy6cq3jPPqjiChkVvvNKmPGJxWUtg6LnF5kejMRNNU3TGtRBeJgk33yuGBxrMPHi"
WIF = "L1aW4aubDFB7yfras2S1mN3bqg9nwySY8nkoLmJebSLD5BWv3ENZ"
DESCRIPTOR = f"wpkh({XPRV}/84h/0h/0h/0/*)"
PASSPHRASE = "my-hot-wallet-file-password"


def test_redact_text_scrubs_xprv_and_wif():
    assert XPRV not in redact_text(f"wpkh({XPRV}/0/*)")
    assert WIF not in redact_text(WIF)
    assert WIF not in redact_text(f"blinded(slip77({WIF}),wsh(...))")
    for prefix in ("yprv", "zprv", "Yprv", "Zprv", "uprv", "vprv"):
        secret = prefix + XPRV[4:]
        assert secret not in redact_text(secret)
    assert '"password": "with spaces"' not in redact_text('"password": "with spaces"')
    assert redact_text("getblockcount") == "getblockcount"


def test_sensitive_rpc_method_is_redacted():
    payload = [{"method": "walletpassphrase", "params": [PASSPHRASE, 60], "id": 0}]
    assert PASSPHRASE not in json.dumps(redact_rpc_payload(payload))


@pytest.mark.parametrize(
    "method,params",
    [
        ("createwallet", ["wallet", False, True, PASSPHRASE, False, True]),
        ("importprivkey", [WIF]),
        ("sethdseed", [True, WIF]),
        ("signrawtransactionwithkey", ["rawtx", [WIF]]),
    ],
)
def test_rpc_methods_with_private_params(method, params):
    assert redact_rpc_payload({"method": method, "params": params}) == [
        {"method": method, "params": REDACTED}
    ]


def test_descriptor_with_xprv_is_redacted():
    payload = [
        {
            "method": "importdescriptors",
            "params": [{"desc": DESCRIPTOR, "timestamp": "now"}],
            "id": 0,
        }
    ]
    redacted = json.dumps(redact_rpc_payload(payload))
    assert XPRV not in redacted
    assert REDACTED in redacted


def test_harmless_call_keeps_its_params():
    payload = [{"method": "getblockchaininfo", "params": [], "id": 0}]
    assert redact_rpc_payload(payload) == [
        {"method": "getblockchaininfo", "params": []}
    ]


def test_wallet_document_is_reduced_to_its_shape():
    document = json.dumps({"keystore": {"seed": "abandon " * 11, "xprv": XPRV}})
    described = redact_wallet_document(document)
    assert "keystore" in described
    assert XPRV not in described
    assert "abandon" not in described
    assert redact_wallet_document("not json at all") == "<unparsable wallet document>"


def test_timeout_log_does_not_contain_the_wallet_passphrase(caplog, monkeypatch):
    session = MagicMock()
    session.post.side_effect = requests.exceptions.Timeout("timed out")
    rpc = BitcoinRPC(
        user="user",
        password="password",
        host="127.0.0.1",
        port=8332,
        protocol="http",
        timeout=1,
        session=session,
    )
    monkeypatch.setattr(BitcoinRPC, "counter", 0)
    monkeypatch.setattr(BitcoinRPC, "last_call_hash", None)
    monkeypatch.setattr(BitcoinRPC, "last_call_hash_counter", 0)

    logger = logging.getLogger("cryptoadvance.specter.rpc")
    with caplog.at_level(logging.ERROR, logger=logger.name):
        with pytest.raises(SpecterError):
            rpc.multi([("createwallet", "w", False, True, PASSPHRASE)], timeout=15)

    assert PASSPHRASE not in caplog.text
    assert "createwallet" in caplog.text


def test_debug_trace_does_not_contain_private_key(caplog, monkeypatch):
    from cryptoadvance.specter import rpc as rpc_module

    monkeypatch.setattr(BitcoinRPC, "last_call_hash", None)
    monkeypatch.setattr(BitcoinRPC, "last_call_hash_counter", 0)
    monkeypatch.setattr(rpc_module.logger, "level", logging.DEBUG)
    session = MagicMock()
    session.post.return_value.status_code = 200
    session.post.return_value.json.return_value = [{"result": True, "error": None}]
    rpc = BitcoinRPC(session=session)
    with caplog.at_level(logging.DEBUG, logger=rpc_module.logger.name):
        rpc.multi([("importprivkey", WIF)])
    assert "payload:" in caplog.text
    assert WIF not in caplog.text


def test_failed_rpc_response_does_not_echo_password(caplog):
    response = MagicMock(status_code=500, text='{"password": "with spaces"}')
    response.json.side_effect = ValueError("invalid JSON")
    session = MagicMock()
    session.post.return_value = response
    rpc = BitcoinRPC(session=session)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(RpcError) as error:
            rpc.multi([("getblockcount",)])
    assert "with spaces" not in caplog.text
    assert "with spaces" not in str(error.value)
    assert "with spaces" not in error.value.error_msg


def test_wallet_import_descriptor_error_does_not_echo_private_key(monkeypatch):
    secret_descriptor = f"wpkh({XPRV}/0/*)"
    monkeypatch.setattr(
        WalletImporter,
        "parse_wallet_data_import",
        lambda data: ("wallet", secret_descriptor, []),
    )
    from embit.descriptor import Descriptor

    def invalid_descriptor(value):
        raise ValueError(f"Invalid descriptor: {value}")

    monkeypatch.setattr(Descriptor, "from_string", invalid_descriptor)
    with pytest.raises(SpecterError) as error:
        WalletImporter("{}", MagicMock(is_liquid=False))
    assert XPRV not in str(error.value)
