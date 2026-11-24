"""Node-free regressions for Liquid funded PSETs and change-address reuse."""

from unittest.mock import Mock, patch

import pytest
from embit.liquid.pset import LOutputScope, PSET
from embit.script import Script

from cryptoadvance.specter.liquid.rpc import LiquidRPC
from cryptoadvance.specter.liquid.wallet import LWallet
from cryptoadvance.specter.rpc import BitcoinRPC


def output(value, blinded):
    scope = LOutputScope()
    scope.value = value
    scope.asset = bytes(32)
    scope.script_pubkey = Script(b"\x51")
    if blinded:
        scope.blinding_pubkey = b"\x02" + bytes(32)
    return scope


@pytest.mark.parametrize(
    "blinded,expected_values",
    [
        (True, [100]),
        (False, [0, 100]),
    ],
)
def test_funded_pset_removes_zero_only_with_blinded_outputs(blinded, expected_values):
    pset = PSET(version=2)
    pset.outputs = [output(0, blinded), output(100, blinded)]
    funded = {"psbt": str(pset)}
    rpc = object.__new__(LiquidRPC)
    with patch.object(
        BitcoinRPC, "__getattr__", return_value=Mock(return_value=funded)
    ) as call:
        result = rpc.walletcreatefundedpsbt([], [], blind=False)

    call.assert_called_once_with("walletcreatefundedpsbt")
    assert [
        out.value for out in PSET.from_string(result["psbt"]).outputs
    ] == expected_values


@pytest.mark.parametrize("unconfirmed_amount,expected_index", [(0.25, 8), (0, 7)])
def test_liquid_change_address_checks_unconfirmed_funds(
    monkeypatch, unconfirmed_amount, expected_index
):
    wallet = object.__new__(LWallet)
    wallet.change_address = "change-address"
    wallet.change_index = 7
    wallet.fetch_transactions = Mock()
    wallet.check_utxo = Mock()
    wallet.get_info = Mock()
    wallet.getnewaddress = Mock()
    rpc = Mock()
    rpc.getreceivedbyaddress.side_effect = lambda address, minconf=1, assetlabel=None: {
        "bitcoin": unconfirmed_amount if minconf == 0 else 0
    }
    monkeypatch.setattr(LWallet, "rpc", property(lambda self: rpc))

    wallet.getdata()

    rpc.getreceivedbyaddress.assert_called_once_with(
        "change-address", minconf=0, assetlabel=None
    )
    assert wallet.change_index == expected_index
    if unconfirmed_amount:
        wallet.getnewaddress.assert_called_once_with(change=True)
    else:
        wallet.getnewaddress.assert_not_called()
