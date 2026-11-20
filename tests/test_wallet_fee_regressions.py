"""Wallet fee regressions without a Bitcoin node."""

from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path

import pytest
from jinja2 import Environment

from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.wallet.wallet import Wallet
from cryptoadvance.specter.liquid.wallet import LWallet


class FundedPSBT:
    def __init__(self, psbt, *args, **kwargs):
        self.base64 = psbt
        self.fee_rate = 7  # Deliberately differs from Core's requested rate.


@pytest.mark.parametrize("wallet_type", [Wallet, LWallet])
def test_core_funds_at_requested_rate_only_once(wallet_type):
    wallet = wallet_type.__new__(wallet_type)
    wallet.PSBTCls = FundedPSBT
    rpc = Mock()
    rpc.getchaintips.return_value = [{"height": 123}]
    rpc.walletcreatefundedpsbt.return_value = {"psbt": "funded"}
    wallet.manager = SimpleNamespace(
        rpc=Mock(), rpc_path="wallets", bitcoin_core_version_raw=210000, chain="main"
    )
    wallet.manager_rpc = wallet.manager.rpc
    wallet._rpc = rpc
    wallet.descriptor = object()
    wallet.keys = []
    wallet._devices = []
    wallet.change_address = "change"
    wallet.change_index = 0
    wallet.address_type = None
    wallet.get_address = Mock(return_value="change")
    wallet.balance = {"trusted": 2, "untrusted_pending": 0, "immature": 0}
    wallet.fill_psbt = Mock(return_value="filled")
    wallet.save_pending_psbt = Mock()

    kwargs = {"assets": ["asset"]} if wallet_type is LWallet else {}
    result = wallet.createpsbt(
        ["destination"], [1], fee_rate=10, rbf_edit_mode=True, **kwargs
    )

    assert result.base64 == ("funded" if wallet_type is LWallet else "filled")
    wallet.rpc.walletcreatefundedpsbt.assert_called_once()
    assert wallet.rpc.walletcreatefundedpsbt.call_args.args[3]["feeRate"] == 0.0001
    wallet.save_pending_psbt.assert_called_once_with(result)


def make_rbf_wallet(output_values, fee=100, size=100, change_index=None):
    wallet = Wallet.__new__(Wallet)
    outputs = [SimpleNamespace(value=value) for value in output_values]
    scopes = [SimpleNamespace(is_change=i == change_index) for i in range(len(outputs))]
    psbt = SimpleNamespace(
        outputs=scopes,
        psbt=SimpleNamespace(outputs=outputs),
        fee=fee,
        full_size=size,
        to_dict=Mock(return_value={"fee_rate": 10}),
    )
    wallet.psbt_from_txid = Mock(return_value=psbt)
    wallet.save_pending_psbt = Mock()
    return wallet, psbt


def test_single_output_bump_warns_recipient_amount_is_reduced():
    wallet, psbt = make_rbf_wallet([2000])

    result = wallet.bumpfee("txid", 10)

    assert psbt.psbt.outputs[0].value == 1100
    assert result["recipient_amount_reduced"] is True
    wallet.save_pending_psbt.assert_called_once_with(psbt)


@pytest.mark.parametrize("amount", [800, 900, 1446])
def test_single_output_bump_refuses_nonpositive_or_dust_remainder(amount):
    wallet, psbt = make_rbf_wallet([amount])

    with pytest.raises(SpecterError, match="Not enough funds"):
        wallet.bumpfee("txid", 10)

    assert psbt.psbt.outputs[0].value == amount
    wallet.save_pending_psbt.assert_not_called()


def test_sign_page_displays_persistent_warning_only_for_reduced_payment():
    template = (
        Path(__file__).resolve().parents[1]
        / "src/cryptoadvance/specter/templates/wallet/send/sign/wallet_send_sign_psbt.jinja"
    ).read_text()
    warning = template.split('<div class="tx_info">', 1)[1].split(
        "{% for i in range(psbt['address']|length) %}", 1
    )[0]
    render = Environment().from_string(warning).render

    assert "reduces the recipient's payment" in render(
        psbt={"recipient_amount_reduced": True}, _=lambda text: text
    )
    assert "reduces the recipient's payment" not in render(psbt={}, _=lambda text: text)


def test_change_output_bump_preserves_recipient():
    wallet, psbt = make_rbf_wallet([2000, 2000], change_index=1)

    result = wallet.bumpfee("txid", 10)

    assert [out.value for out in psbt.psbt.outputs] == [2000, 1100]
    assert not result.get("recipient_amount_reduced")
