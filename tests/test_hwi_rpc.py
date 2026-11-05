""" This is just a manual test to understand how HWI works. All tests are marked skipped as hardware plugged in is necessary.
    Don't take this as best practise. This is just something to test difference in behaviour for migration from HWI 2.0.2 to 2.1.0

    To get it to run:
    * comment the test: @pytest.mark.skip()
    * Plugin yout trezor
    * Run the test like: pytest tests/test_hwi_rpc.py::test_enumerate_trezor  -vv -s
    * Type in your Pin
    * Success!
"""

import logging
import io
import pytest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from hwilib.common import Chain
from hwilib.errors import ActionCanceledError

from cryptoadvance.specter.hwi_rpc import HWIBridge
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.util.descriptor import Descriptor


# A real, base58check-valid xpub. convert_xpub_prefix() runs
# base58.decode_check() on whatever to_string() returns and re-encodes it
# with the slip132 prefix, so this has to actually decode - a "looks like
# an xpub" placeholder silently fails that conversion, _extract_xpubs_from_
# client() swallows the per-key exception, and the test then asserts only
# on which *paths* were requested while zero keys actually came back.
_VALID_XPUB = (
    "xpub661MyMwAqRbcEwCMnGLoVvi19EZQaXijFpNzxCgpC4Cs1onmKcddCwMH6P8DicQYDm"
    "GjAcu5pNNciH3m5CFuZq2LmdNM4EYK9bqY5BFimfo"
)


class _FakeExtKey:
    def __init__(self, path):
        self._path = path

    def to_string(self):
        return _VALID_XPUB


class _FakeDiyClient:
    """Minimal stand-in for SpecterClient with the batch-auth API."""

    def __init__(self, network):
        # network the (fake) device is currently on: "main" or "test"
        self._network = network
        self.chain = Chain.MAIN
        self.calls = []

    def get_master_fingerprint(self):
        return bytes.fromhex("00000000")

    def begin_xpub_authorization(self, paths):
        self.calls.append(("begin", list(paths)))
        coin = "0h" if self._network == "main" else "1h"
        if all("/%s/" % coin in p or p.endswith("/%s" % coin) for p in paths):
            return True
        return False  # scope for the other network -> rejected

    def end_xpub_authorization(self):
        self.calls.append(("end", None))

    def get_pubkey_at_path(self, path):
        self.calls.append(("xpub", path))
        return _FakeExtKey(path)

    def close(self):
        self.calls.append(("close", None))


class _FakePlainClient:
    """Stand-in for a client without the batch-auth API (e.g. Trezor)."""

    def __init__(self):
        self.chain = Chain.MAIN
        self.calls = []

    def get_master_fingerprint(self):
        return bytes.fromhex("00000000")

    def get_pubkey_at_path(self, path):
        self.calls.append(("xpub", path))
        return _FakeExtKey(path)

    def close(self):
        self.calls.append(("close", None))


def _paths_requested(client):
    return [p for kind, p in client.calls if kind == "xpub"]


def _key_lines(result):
    """The '[fpr/derivation]xpub' lines actually returned to the caller."""
    return [ln for ln in result.split("\n") if ln.strip()]


def test_extract_xpubs_mainnet_diy_confirms_once_and_skips_testnet():
    client = _FakeDiyClient("main")
    result = HWIBridge(skip_hwi_initialisation=True)._extract_xpubs_from_client(client)

    kinds = [k for k, _ in client.calls]
    assert kinds.count("begin") == 1  # single scoped confirmation
    assert ("end", None) in client.calls
    paths = _paths_requested(client)
    assert paths == [
        "m/49h/0h/0h",
        "m/84h/0h/0h",
        "m/48h/0h/0h/1h",
        "m/48h/0h/0h/2h",
    ]  # only the network the device is on, no testnet requests

    # and the keys actually came back, one line per requested path, with
    # the slip132 prefix conversion applied (not swallowed as an error)
    lines = _key_lines(result)
    assert len(lines) == 4
    assert [ln.split("]")[0] + "]" for ln in lines] == [
        "[00000000/49'/0'/0']",
        "[00000000/84'/0'/0']",
        "[00000000/48'/0'/0'/1']",
        "[00000000/48'/0'/0'/2']",
    ]
    assert lines[0].split("]")[1].startswith("ypub")
    assert lines[1].split("]")[1].startswith("zpub")
    assert lines[2].split("]")[1].startswith("Ypub")
    assert lines[3].split("]")[1].startswith("Zpub")


def test_extract_xpubs_testnet_diy_confirms_once_and_skips_mainnet():
    client = _FakeDiyClient("test")
    result = HWIBridge(skip_hwi_initialisation=True)._extract_xpubs_from_client(client)

    assert _paths_requested(client) == [
        "m/49h/1h/0h",
        "m/84h/1h/0h",
        "m/48h/1h/0h/1h",
        "m/48h/1h/0h/2h",
    ]
    lines = _key_lines(result)
    assert len(lines) == 4
    assert [ln.split("]")[0] + "]" for ln in lines] == [
        "[00000000/49'/1'/0']",
        "[00000000/84'/1'/0']",
        "[00000000/48'/1'/0'/1']",
        "[00000000/48'/1'/0'/2']",
    ]
    assert lines[0].split("]")[1].startswith("upub")
    assert lines[1].split("]")[1].startswith("vpub")
    assert lines[2].split("]")[1].startswith("Upub")
    assert lines[3].split("]")[1].startswith("Vpub")


def test_extract_xpubs_without_batch_auth_still_fetches_both_networks():
    client = _FakePlainClient()
    result = HWIBridge(skip_hwi_initialisation=True)._extract_xpubs_from_client(client)

    assert _paths_requested(client) == [
        "m/49h/0h/0h",
        "m/84h/0h/0h",
        "m/48h/0h/0h/1h",
        "m/48h/0h/0h/2h",
        "m/49h/1h/0h",
        "m/84h/1h/0h",
        "m/48h/1h/0h/1h",
        "m/48h/1h/0h/2h",
    ]
    assert len(_key_lines(result)) == 8  # all 8 keys converted and returned


def test_extract_xpubs_diy_cancellation_propagates():
    client = _FakeDiyClient("main")
    client.begin_xpub_authorization = MagicMock(side_effect=ActionCanceledError("nope"))
    with pytest.raises(ActionCanceledError):
        HWIBridge(skip_hwi_initialisation=True)._extract_xpubs_from_client(client)
    assert ("close", None) in client.calls  # client still cleaned up


@contextmanager
def _fake_client_cm(client):
    yield client


def test_begin_xpub_authorization_rejects_a_non_bip32_path():
    bridge = HWIBridge(skip_hwi_initialisation=True)
    with pytest.raises(Exception):
        # never reaches the device - parsed and rejected at the RPC boundary
        bridge.begin_xpub_authorization(paths=["m/49h/0h/0h;m/84h/0h/0h"])


def test_begin_xpub_authorization_normalises_paths_before_the_device_sees_them():
    bridge = HWIBridge(skip_hwi_initialisation=True)
    client = _FakeDiyClient("main")
    with patch.object(bridge, "_get_client", return_value=_fake_client_cm(client)):
        bridge.begin_xpub_authorization(paths=["m/49'/0'/0'", "m/84h/0h/0h"])
    assert client.calls[0] == ("begin", ["m/49h/0h/0h", "m/84h/0h/0h"])


class _OneShotClient:
    def __init__(self, exc):
        self.chain = None
        self._exc = exc

    def get_master_fingerprint(self):
        return bytes.fromhex("00000000")

    def get_pubkey_at_path(self, path):
        raise self._exc


def _extract_one(exc):
    bridge = HWIBridge(skip_hwi_initialisation=True)
    with patch.object(
        bridge, "_get_client", return_value=_fake_client_cm(_OneShotClient(exc))
    ):
        return bridge.jsonrpc(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "extract_xpub",
                "params": {"derivation": "m/84h/0h/0h", "device_type": "specter"},
            }
        )


def test_extract_xpub_returns_none_when_the_user_cancels():
    resp = _extract_one(ActionCanceledError("nope"))
    assert "error" not in resp
    assert resp["result"] is None  # caller reads this as "cancelled, stop"


def test_extract_xpub_propagates_other_failures_instead_of_swallowing_them():
    from cryptoadvance.specter.devices.hwi.specter_diy import (
        SpecterDIYNetworkMismatchError,
    )

    for exc in (
        SpecterDIYNetworkMismatchError("test", "switch the device to Mainnet"),
        RuntimeError("transport blew up"),
    ):
        resp = _extract_one(exc)
        assert "error" in resp  # reaches the UI, not an ambiguous None


@pytest.mark.skip()
def test_trezor(caplog, monkeypatch):
    """In order to get this test working, you have to run it with "-s":
    pytest tests/test_hwi_rpc.py::test_enumerate_trezor  -vv -s
    """
    caplog.set_level(logging.DEBUG)

    hwi = HWIBridge()
    # bla = hwi.detect_device()

    res = hwi.enumerate(passphrase="")[0]
    print(res)
    # seems to be normal
    assert res["type"] == "trezor"
    assert res["model"] == "trezor_1"
    assert res["path"].startswith("webusb:003:1:1:")

    if res["needs_pin_sent"]:
        assert res["error"].startswith(
            "Could not open client or get fingerprint information: Trezor is locked"
        )
        res = hwi.prompt_pin(device_type="trezor", passphrase="")
        assert res["success"] == True
        # monkeypatch.setattr('sys.stdin', io.StringIO('my input'))
        pin = input("Enter pin: ")

        res = hwi.send_pin(pin, device_type="trezor", passphrase="")
        assert res["success"] == True

    else:
        assert res["error"].startswith(
            "Could not open client or get fingerprint information: Passphrase needs to be specified before the fingerprint information can be retrieved"
        )
        assert len(res["fingerprint"]) == 8
    results = hwi.extract_xpubs(chain="test", device_type="trezor").split("\n")
    assert len(results) == 9
    assert results[0].startswith("[")
    print(results[0])
    # You can construct keys from the results:
    key: Key = Key.parse_xpub(results[0])
    assert len(key.fingerprint) == 8
    assert key.derivation == "m/49h/0h/0h"
    assert key.xpub.startswith("xpub")


@pytest.mark.skip()
def test_jade(caplog):
    caplog.set_level(logging.DEBUG)

    hwi = HWIBridge()
    # bla = hwi.detect_device()

    res = hwi.enumerate(passphrase="")[0]

    # seems to be normal
    assert res["type"] == "jade"
    assert res["model"] == "jade"
    assert res["path"] == "/dev/ttyUSB0"
    assert res["error"].startswith(
        "Could not open client or get fingerprint information: __init__() got an unexpected keyword argument 'timeout'"
    )
    assert res["code"] == -13
    assert res["fingerprint"] == "4c6de3ce"

    results = hwi.extract_xpubs(
        chain="main", device_type="jade", path="/dev/ttyUSB0"
    ).split("\n")
    assert len(results) == 9
    assert results[0].startswith("[")
