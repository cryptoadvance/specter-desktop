"""
Regression tests for https://github.com/cryptoadvance/specter-desktop/issues/2604

Bitcoin Core's legacy `importmulti` refuses to shrink the keypool range of an
already-imported descriptor ("new range must include current range"). This can
surface when re-creating a wallet under a name that Core already has a wider
range recorded for. Wallet.create should detect that specific rejection and
retry once with a range wide enough to include Core's current range, instead
of failing outright.

These tests mock the RPC layer entirely, so they don't need a running
bitcoind/regtest node.
"""

from unittest.mock import MagicMock

from cryptoadvance.specter.key import Key
from cryptoadvance.specter.wallet import Wallet


def _make_rpc(importmulti_responses):
    """Builds a fake `rpc`/`wallet_rpc` pair.

    importmulti_responses: a list of return values, one per call to
    `importmulti`. Each element is itself the list-of-dicts the real RPC
    would return.
    """
    wallet_rpc = MagicMock()
    wallet_rpc.importmulti.side_effect = importmulti_responses

    rpc = MagicMock()
    rpc.getnetworkinfo.return_value = {"version": 200000}  # pre-descriptor-wallets
    rpc.wallet.return_value = wallet_rpc
    return rpc, wallet_rpc


class _BareWallet(Wallet):
    """A stand-in for Wallet that skips the real __init__ (which touches
    rpc, address lists, tx history, etc.) so these tests only exercise the
    `create()` classmethod's import/retry logic."""

    def __init__(self, *args, **kwargs):
        self.init_args = args
        self.init_kwargs = kwargs


def _single_sig_key():
    # A known-good testnet tpub (m/84'/1'/0') used elsewhere in the test
    # suite's ghost-machine fixtures.
    tpub = "tpubDC4DsqH5rqHqipMNqUbDFtQT3AkKkUrvLsN6miySvortU3s1LGaNVAb7wX2No2VsuxQV82T8s3HJLv3kdx1CPjsJ3onC1Zo5mWCQzRVaWVX"
    return Key.parse_xpub(f"[81f802e3/84h/1h/0h]{tpub}")


def test_create_retries_with_widened_range_on_shrink_refusal():
    """Core rejects the default [0, GAP_LIMIT] range because it already has
    a wider range on file; Wallet.create should retry with a widened range
    and succeed."""
    key = _single_sig_key()

    shrink_refusal = [
        {
            "success": False,
            "error": {"message": "new range must include current range = [0,1008]"},
        },
        {
            "success": False,
            "error": {"message": "new range must include current range = [0,1000]"},
        },
    ]
    success = [{"success": True}, {"success": True}]

    rpc, wallet_rpc = _make_rpc([shrink_refusal, success])

    wallet = _BareWallet.create(
        rpc=rpc,
        rpc_path="specter",
        working_folder="/tmp",
        device_manager=MagicMock(),
        wallet_manager=MagicMock(),
        name="mywallet",
        alias="mywallet",
        sigs_required=1,
        key_type="wpkh",
        keys=[key],
        devices=[MagicMock()],
        core_version=200000,
    )

    assert wallet is not None
    # One retry: the first call (default range) failed, the second (widened
    # range) succeeded.
    assert wallet_rpc.importmulti.call_count == 2
    second_call_args = wallet_rpc.importmulti.call_args_list[1][0][0]
    # Widened range must cover the widest range Core reported (1008)
    assert all(arg["range"] == [0, 1008] for arg in second_call_args)


def test_create_raises_if_retry_also_fails():
    """If the widened-range retry still fails, Wallet.create should still
    raise a SpecterError (no silent swallow of a real problem)."""
    from cryptoadvance.specter.specter_error import SpecterError

    key = _single_sig_key()

    shrink_refusal = [
        {
            "success": False,
            "error": {"message": "new range must include current range = [0,1008]"},
        },
    ]
    still_failing = [
        {
            "success": False,
            "error": {"message": "some other unrelated error"},
        },
    ]

    rpc, wallet_rpc = _make_rpc([shrink_refusal, still_failing])

    try:
        _BareWallet.create(
            rpc=rpc,
            rpc_path="specter",
            working_folder="/tmp",
            device_manager=MagicMock(),
            wallet_manager=MagicMock(),
            name="mywallet",
            alias="mywallet",
            sigs_required=1,
            key_type="wpkh",
            keys=[key],
            devices=[MagicMock()],
            core_version=200000,
        )
        assert False, "expected SpecterError"
    except SpecterError:
        pass

    assert wallet_rpc.importmulti.call_count == 2


def test_create_does_not_retry_on_unrelated_failure():
    """A failure that isn't the range-shrink message should raise immediately,
    without a pointless retry."""
    from cryptoadvance.specter.specter_error import SpecterError

    key = _single_sig_key()

    unrelated_failure = [
        {
            "success": False,
            "error": {"message": "some other unrelated error"},
        },
    ]

    rpc, wallet_rpc = _make_rpc([unrelated_failure])

    try:
        _BareWallet.create(
            rpc=rpc,
            rpc_path="specter",
            working_folder="/tmp",
            device_manager=MagicMock(),
            wallet_manager=MagicMock(),
            name="mywallet",
            alias="mywallet",
            sigs_required=1,
            key_type="wpkh",
            keys=[key],
            devices=[MagicMock()],
            core_version=200000,
        )
        assert False, "expected SpecterError"
    except SpecterError:
        pass

    assert wallet_rpc.importmulti.call_count == 1
