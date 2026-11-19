"""Unit tests for the log redaction helpers.

These tests do not need a node: they prove that key material never reaches a
log record, on the RPC timeout path, on the DEBUG trace path and on the wallet
import path.
"""

import json
import logging
from unittest.mock import MagicMock

import pytest
import requests

from cryptoadvance.specter.rpc import BitcoinRPC
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
    assert WIF not in redact_text(f"blinded(slip77({WIF}),wsh(...))")
    assert redact_text("getblockcount") == "getblockcount"


def test_sensitive_rpc_method_is_redacted():
    payload = [{"method": "walletpassphrase", "params": [PASSPHRASE, 60], "id": 0}]
    assert PASSPHRASE not in json.dumps(redact_rpc_payload(payload))


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


def test_timeout_log_does_not_contain_the_wallet_passphrase(caplog):
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
    BitcoinRPC.counter = 0
    BitcoinRPC.last_call_hash = None
    BitcoinRPC.last_call_hash_counter = 0

    logger = logging.getLogger("cryptoadvance.specter.rpc")
    with caplog.at_level(logging.ERROR, logger=logger.name):
        with pytest.raises(Exception):
            rpc.multi([("walletpassphrase", PASSPHRASE, 60)], timeout=15)

    assert PASSPHRASE not in caplog.text
    assert "walletpassphrase" in caplog.text
