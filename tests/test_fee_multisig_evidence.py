"""RBF regressions for the fee correction PR; real Core fee evidence lives in test_fee_multisig_core.py."""
from unittest.mock import Mock
import pytest
from embit import bip32, networks
from embit.descriptor import Descriptor
from embit.psbt import PSBT, DerivationPath
from embit.script import address_to_scriptpubkey
from embit.transaction import Transaction, TransactionInput, TransactionOutput
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.util.psbt import SpecterPSBT
from cryptoadvance.specter.wallet.wallet import Wallet

FEE_RATE = 10.0
RECIPIENT = "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
KEYS = [bip32.HDKey.from_seed(seed).to_public().to_base58() for seed in (b"specter-multisig-1", b"specter-multisig-2", b"specter-multisig-3")]

def descriptor_for(kind):
    return Descriptor.from_string("wsh(sortedmulti(2,%s/{0,1}/*,%s/{0,1}/*,%s/{0,1}/*))" % tuple(KEYS))

def make_pending_psbt(descriptor, output_values, change_index):
    """Real PSBT; ``change_index`` marks that output through bip32 derivations."""
    tx = Transaction(
        vin=[TransactionInput(b"\x33" * 32, 1)],
        vout=[
            TransactionOutput(value, address_to_scriptpubkey(RECIPIENT))
            for value in output_values
        ],
    )
    if change_index is not None:
        change_script = descriptor.branch(1).derive(0).script_pubkey()
        tx.vout[change_index] = TransactionOutput(
            output_values[change_index], change_script
        )
    psbt = PSBT(tx)
    psbt.inputs[0].witness_utxo = TransactionOutput(
        sum(output_values) + 1000,  # pending transaction paid a 1000 sat fee
        descriptor.branch(0).derive(0).script_pubkey(),
    )
    if change_index is not None:
        fingerprint = descriptor.keys[0].my_fingerprint
        change = descriptor.derive(0, branch_index=1)
        psbt.outputs[change_index].bip32_derivations[
            change.keys[0].get_public_key()
        ] = DerivationPath(fingerprint, [1, 0])
    return SpecterPSBT(psbt, descriptor, networks.NETWORKS["main"])


def bump_wallet(psbt):
    wallet = Wallet.__new__(Wallet)
    wallet.descriptor = descriptor_for("wsh")
    wallet.psbt_from_txid = Mock(return_value=psbt)
    wallet.save_pending_psbt = Mock()
    return wallet


def test_bumpfee_reduces_change_output_not_last_recipient():
    """Change sits at index 1 of 3: only that output may shrink.

    The change index is found by scanning ``psbt.outputs`` for ``is_change``,
    so the recipient outputs before and after it must stay untouched.
    """
    descriptor = descriptor_for("wsh")
    psbt = make_pending_psbt(descriptor, [50_000, 40_000, 30_000], change_index=1)
    wallet = bump_wallet(psbt)
    fee_delta = round(FEE_RATE * 2 * psbt.full_size - psbt.fee)
    original_fee = psbt.fee

    result = wallet.bumpfee("txid", FEE_RATE * 2)

    assert [out.value for out in psbt.psbt.outputs] == [
        50_000,
        40_000 - fee_delta,
        30_000,
    ]
    assert psbt.fee == original_fee + fee_delta
    assert not result.get("recipient_amount_reduced")


def test_bumpfee_single_output_reduces_recipient_and_says_so():
    """No change output: the recipient absorbs the whole fee delta."""
    descriptor = descriptor_for("wsh")
    psbt = make_pending_psbt(descriptor, [99_000], change_index=None)
    wallet = bump_wallet(psbt)
    fee_delta = round(FEE_RATE * 2 * psbt.full_size - psbt.fee)
    recipient_script = psbt.psbt.outputs[0].script_pubkey

    result = wallet.bumpfee("txid", FEE_RATE * 2)

    assert psbt.psbt.outputs[0].value == 99_000 - fee_delta
    assert psbt.psbt.outputs[0].script_pubkey == recipient_script
    assert result["recipient_amount_reduced"] is True


@pytest.mark.parametrize("value", [600, 900])
def test_bumpfee_single_output_refuses_dust_or_negative_remainder(value):
    descriptor = descriptor_for("wsh")
    psbt = make_pending_psbt(descriptor, [value], change_index=None)
    wallet = bump_wallet(psbt)

    with pytest.raises(SpecterError, match="Not enough funds"):
        wallet.bumpfee("txid", FEE_RATE * 2)

    assert psbt.psbt.outputs[0].value == value
    assert not getattr(psbt, "recipient_amount_reduced", False)
    wallet.save_pending_psbt.assert_not_called()


def test_combined_single_output_guard_and_persisted_warning():
    """An accepted bump persists its warning; a rejected bump changes nothing."""
    descriptor = descriptor_for("wsh")
    psbt = make_pending_psbt(descriptor, [99_000], change_index=None)
    wallet = bump_wallet(psbt)

    result = wallet.bumpfee("txid", FEE_RATE * 2)
    wallet.save_pending_psbt.assert_called_once_with(psbt)
    assert result["recipient_amount_reduced"] is True
    restored = SpecterPSBT.from_dict(result, descriptor, networks.NETWORKS["main"])
    assert restored.recipient_amount_reduced is True
    assert restored.to_dict()["recipient_amount_reduced"] is True

    unsafe = make_pending_psbt(descriptor, [600], change_index=None)
    unsafe_wallet = bump_wallet(unsafe)
    with pytest.raises(SpecterError, match="Not enough funds"):
        unsafe_wallet.bumpfee("txid", FEE_RATE * 2)
    assert unsafe.psbt.outputs[0].value == 600
    unsafe_wallet.save_pending_psbt.assert_not_called()
