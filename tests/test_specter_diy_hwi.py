"""
Regression tests for cryptoadvance.specter.devices.hwi.specter_diy.SpecterClient.

Specter DIY firmware now requires an on-device user confirmation before
returning an xpub, so get_pubkey_at_path() must not impose the old 3-second
response timeout (it should wait indefinitely, like sign_tx() already does).
get_master_fingerprint() stays non-interactive and keeps its short timeout.

These are pure unit tests against a mocked transport - no bitcoind, no real
device, no network required.
"""
from unittest.mock import MagicMock

from hwilib.common import Chain

from cryptoadvance.specter.devices.hwi.specter_diy import SpecterClient


def _client_with_mocked_transport():
    # ":" in the path selects the (non-connecting-on-init) simulator transport
    client = SpecterClient("127.0.0.1:9999")
    client.chain = Chain.MAIN
    client.dev.query = MagicMock(return_value="deadbeef")
    return client


def test_get_pubkey_at_path_does_not_pass_a_timeout():
    client = _client_with_mocked_transport()
    client.dev.query.return_value = (
        "tpubD6NzVbkrYhZ4WZaiWHz59q5EQ61bd6dUYfU4ggRWAtNAyyYRNWT6ktJ7UHJEXURvSCVW"
        "shSCLtQ4pnyNSSVUXQfP7yzzKcVXBEeejuSsn7q"
    )
    client.get_pubkey_at_path("m/84h/0h/0h")
    args, kwargs = client.dev.query.call_args
    # positional call: self.dev.query(data, timeout) - the timeout arg
    # (positional or via kwarg) must be None, i.e. "wait indefinitely"
    passed_timeout = kwargs.get("timeout", args[1] if len(args) > 1 else None)
    assert passed_timeout is None


def test_get_master_fingerprint_keeps_bounded_timeout():
    client = _client_with_mocked_transport()
    client.get_master_fingerprint()
    args, kwargs = client.dev.query.call_args
    passed_timeout = kwargs.get("timeout", args[1] if len(args) > 1 else None)
    assert passed_timeout == SpecterClient.TIMEOUT
