"""Merging signed PSBTs must keep signatures without trusting their metadata."""

import pytest
from embit import ec
from embit.psbt import PSBT, DerivationPath
from embit.script import Script, Witness
from embit.transaction import Transaction, TransactionInput, TransactionOutput

from cryptoadvance.specter.util.psbt import SpecterPSBT

TAPROOT_KEY_SIG = b"\x13"
TAPROOT_SCRIPT_SIG = b"\x14"
TAPROOT_LEAF_SCRIPT = b"\x18"
PROPRIETARY = b"\xfc\x07specter\x00"

P2TR_SCRIPT = Script(b"\x51\x20" + b"\x03" * 32)


def psbt_from_tx(tx):
    """Build a PSBT whose scopes have independent `unknown` dicts."""
    return PSBT.parse(PSBT(tx).serialize())


def pending(inputs=1):
    tx = Transaction(
        vin=[TransactionInput(b"\x01" * 32, i) for i in range(inputs)],
        vout=[TransactionOutput(900, Script(b"\x00\x14" + b"\x02" * 20))],
    )
    psbt = psbt_from_tx(tx)
    for inp in psbt.inputs:
        inp.witness_utxo = TransactionOutput(1000, P2TR_SCRIPT)
    return SpecterPSBT(psbt, None, None)


def test_merge_keeps_taproot_key_path_signature_in_its_own_input():
    stored = pending(inputs=2)
    incoming = PSBT.parse(stored.psbt.serialize())
    signature = b"\x11" * 64
    incoming.inputs[1].unknown[TAPROOT_KEY_SIG] = signature

    stored.update(str(incoming))

    assert stored.psbt.inputs[1].unknown[TAPROOT_KEY_SIG] == signature
    assert TAPROOT_KEY_SIG not in stored.psbt.inputs[0].unknown
    # The merged signature survives a save/load round trip of the pending PSBT.
    reopened = PSBT.parse(stored.psbt.serialize())
    assert reopened.inputs[1].unknown[TAPROOT_KEY_SIG] == signature


def test_merge_keeps_taproot_script_path_signature():
    stored = pending()
    incoming = PSBT.parse(stored.psbt.serialize())
    key = TAPROOT_SCRIPT_SIG + b"\x04" * 32 + b"\x05" * 32
    incoming.inputs[0].unknown[key] = b"\x12" * 65

    stored.update(str(incoming))

    assert stored.psbt.inputs[0].unknown[key] == b"\x12" * 65


def test_merge_keeps_taproot_signature_with_sighash_byte():
    stored = pending()
    incoming = PSBT.parse(stored.psbt.serialize())
    incoming.inputs[0].unknown[TAPROOT_KEY_SIG] = b"\x13" * 65

    stored.update(str(incoming))

    assert stored.psbt.inputs[0].unknown[TAPROOT_KEY_SIG] == b"\x13" * 65


def test_merge_does_not_replace_an_already_collected_taproot_signature():
    stored = pending()
    stored.psbt.inputs[0].unknown[TAPROOT_KEY_SIG] = b"\xaa" * 64
    incoming = PSBT.parse(stored.psbt.serialize())
    incoming.inputs[0].unknown[TAPROOT_KEY_SIG] = b"\xbb" * 64

    stored.update(str(incoming))

    assert stored.psbt.inputs[0].unknown[TAPROOT_KEY_SIG] == b"\xaa" * 64


@pytest.mark.parametrize("length", [0, 32, 63, 66])
def test_merge_ignores_malformed_taproot_signature(length):
    stored = pending()
    incoming = PSBT.parse(stored.psbt.serialize())
    incoming.inputs[0].unknown[TAPROOT_KEY_SIG] = b"\x11" * length

    stored.update(str(incoming))

    assert TAPROOT_KEY_SIG not in stored.psbt.inputs[0].unknown


@pytest.mark.parametrize(
    "key,value",
    [
        (TAPROOT_LEAF_SCRIPT + b"\xc0" + b"\x20" * 32, b"\x51"),
        (PROPRIETARY, b"payload"),
        (b"\x0d", b"whatever"),
    ],
)
def test_merge_ignores_other_unknown_fields(key, value):
    stored = pending()
    incoming = PSBT.parse(stored.psbt.serialize())
    incoming.inputs[0].unknown[key] = value

    stored.update(str(incoming))

    assert key not in stored.psbt.inputs[0].unknown


def test_merge_rejects_other_unsigned_transaction_without_mutation():
    stored = pending()
    tx = Transaction.parse(stored.psbt.tx.serialize())
    tx.vout[0].value = 500
    incoming = psbt_from_tx(tx)
    incoming.inputs[0].unknown[TAPROOT_KEY_SIG] = b"\x11" * 64
    with pytest.raises(ValueError, match="unsigned transaction"):
        stored.update(str(incoming))
    assert stored.psbt.outputs[0].value == 900
    assert TAPROOT_KEY_SIG not in stored.psbt.inputs[0].unknown

def test_merge_rejects_final_fields():
    stored = pending()
    incoming = PSBT.parse(stored.psbt.serialize())
    incoming.inputs[0].final_scriptwitness = Witness([b"fake"])
    incoming.inputs[0].unknown[TAPROOT_KEY_SIG] = b"\x11" * 64
    with pytest.raises(ValueError, match="final"):
        stored.update(str(incoming))
    assert stored.psbt.inputs[0].final_scriptwitness is None
    assert TAPROOT_KEY_SIG not in stored.psbt.inputs[0].unknown

def test_finalized_psbt_with_matching_raw_keeps_untrusted_final_fields_out():
    stored = pending()
    incoming = PSBT.parse(stored.psbt.serialize())
    incoming.inputs[0].final_scriptwitness = Witness([b"sig"])
    incoming.inputs[0].unknown[TAPROOT_KEY_SIG] = b"\x11" * 64
    tx = Transaction.parse(stored.psbt.tx.serialize())
    tx.vin[0].witness = Witness([b"sig"])

    stored.update(str(incoming), {"hex": tx.serialize().hex()})

    assert stored.raw == tx.serialize()
    assert stored.psbt.inputs[0].final_scriptwitness is None
    assert stored.psbt.inputs[0].unknown[TAPROOT_KEY_SIG] == b"\x11" * 64


def test_merge_taproot_signature_with_sighash_default():
    stored = pending()
    incoming = PSBT.parse(stored.psbt.serialize())
    incoming.inputs[0].sighash_type = 0
    incoming.inputs[0].unknown[TAPROOT_KEY_SIG] = b"\x11" * 64
    stored.update(str(incoming))
    assert stored.psbt.inputs[0].unknown[TAPROOT_KEY_SIG] == b"\x11" * 64


@pytest.mark.parametrize("length", [0, 32, 63, 66])
def test_merge_ignores_malformed_taproot_script_key(length):
    stored = pending()
    incoming = PSBT.parse(stored.psbt.serialize())
    key = TAPROOT_SCRIPT_SIG + b"\x04" * length
    incoming.inputs[0].unknown[key] = b"\x11" * 64
    stored.update(str(incoming))
    assert key not in stored.psbt.inputs[0].unknown
