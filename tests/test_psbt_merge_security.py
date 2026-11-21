import pytest
from embit import ec
from embit.psbt import PSBT, DerivationPath
from embit.script import Script, Witness
from embit.transaction import Transaction, TransactionInput, TransactionOutput

from cryptoadvance.specter.util.psbt import SpecterPSBT


def pending():
    tx = Transaction(
        vin=[TransactionInput(b"\x01" * 32, 0)],
        vout=[TransactionOutput(900, Script(b"\x00\x14" + b"\x02" * 20))],
    )
    psbt = PSBT(tx)
    psbt.inputs[0].witness_utxo = TransactionOutput(
        1000, Script(b"\x00\x14" + b"\x03" * 20)
    )
    return SpecterPSBT(psbt, None, None)


def test_merge_keeps_transaction_and_utxo_and_accepts_signatures():
    stored = pending()
    incoming = PSBT.parse(stored.psbt.serialize())
    pub = ec.PrivateKey(b"\x01" * 32).get_public_key()
    incoming.inputs[0].partial_sigs[pub] = b"signature"
    incoming.inputs[0].bip32_derivations[pub] = DerivationPath(b"\x01" * 4, [1])
    incoming.inputs[0].witness_utxo = TransactionOutput(999999, Script(b"\x51"))
    stored.update(str(incoming))
    assert stored.psbt.inputs[0].partial_sigs[pub] == b"signature"
    assert stored.psbt.inputs[0].bip32_derivations[pub].derivation == [1]
    assert stored.psbt.inputs[0].witness_utxo.value == 1000
    assert stored.psbt.outputs[0].value == 900
    assert stored.psbt.outputs[0].script_pubkey == stored.psbt.tx.vout[0].script_pubkey


def test_merge_rejects_changed_v2_output_scope():
    stored = pending()
    incoming = PSBT.parse(stored.psbt.serialize())
    incoming.version = 2
    incoming.outputs[0].value = 1
    with pytest.raises(ValueError, match="unsigned transaction"):
        stored.update(str(incoming))
    assert stored.psbt.outputs[0].value == 900


def test_trusted_wallet_rpc_fills_utxo_but_cannot_change_unsigned_transaction():
    stored = pending()
    stored.psbt.inputs[0].witness_utxo = None
    rpc_psbt = pending().psbt
    stored.update(str(rpc_psbt), trusted=True)
    assert stored.psbt.inputs[0].witness_utxo.value == 1000
    changed_tx = Transaction.parse(stored.psbt.tx.serialize())
    changed_tx.vout[0].value = 500
    with pytest.raises(ValueError, match="unsigned transaction"):
        stored.update(str(PSBT(changed_tx)), trusted=True)


def test_trusted_core_enrichment_accepts_finalized_history_metadata():
    stored = pending()
    rpc_psbt = PSBT.parse(stored.psbt.serialize())
    rpc_psbt.inputs[0].final_scriptwitness = Witness([b"sig"])
    stored.update(str(rpc_psbt), trusted=True)
    assert stored.psbt.inputs[0].final_scriptwitness.items == [b"sig"]
    untrusted = pending()
    with pytest.raises(ValueError, match="final fields"):
        untrusted.update(str(rpc_psbt))


def test_merge_rejects_other_unsigned_transaction_without_mutation():
    stored = pending()
    tx = Transaction.parse(stored.psbt.tx.serialize())
    tx.vout[0].value = 500
    incoming = PSBT(tx)
    with pytest.raises(ValueError, match="unsigned transaction"):
        stored.update(str(incoming))
    assert stored.psbt.outputs[0].value == 900


@pytest.mark.parametrize("sighash", [2, 3, 0x81])
def test_merge_rejects_non_all_sighash(sighash):
    stored = pending()
    incoming = PSBT.parse(stored.psbt.serialize())
    incoming.inputs[0].sighash_type = sighash
    with pytest.raises(ValueError, match="sighash"):
        stored.update(str(incoming))
    assert stored.psbt.inputs[0].sighash_type is None


def test_merge_rejects_final_fields():
    stored = pending()
    incoming = PSBT.parse(stored.psbt.serialize())
    incoming.inputs[0].final_scriptwitness = Witness([b"fake"])
    with pytest.raises(ValueError, match="final"):
        stored.update(str(incoming))
    assert stored.psbt.inputs[0].final_scriptwitness is None


def test_raw_transaction_must_match_unsigned_transaction():
    stored = pending()
    other = Transaction(
        vin=[TransactionInput(b"\x04" * 32, 0, witness=Witness([b"sig"]))],
        vout=[TransactionOutput(900, Script(b"\x00\x14" + b"\x02" * 20))],
    )
    with pytest.raises(ValueError, match="transaction"):
        stored.update(None, {"hex": other.serialize().hex()})
    assert stored.raw is None


def test_finalized_raw_transaction_with_witness_is_accepted():
    stored = pending()
    tx = Transaction.parse(stored.psbt.tx.serialize())
    tx.vin[0].witness = Witness([b"sig"])
    stored.update(None, {"hex": tx.serialize().hex()})
    assert stored.raw == tx.serialize()


def test_finalized_psbt_with_matching_raw_keeps_untrusted_final_fields_out():
    stored = pending()
    incoming = PSBT.parse(stored.psbt.serialize())
    incoming.inputs[0].final_scriptwitness = Witness([b"sig"])
    tx = Transaction.parse(stored.psbt.tx.serialize())
    tx.vin[0].witness = Witness([b"sig"])
    stored.update(str(incoming), {"hex": tx.serialize().hex()})
    assert stored.raw == tx.serialize()
    assert stored.psbt.inputs[0].final_scriptwitness is None


def test_recipient_reduction_warning_survives_psbt_serialization():
    stored = pending()
    stored.recipient_amount_reduced = True
    reopened = SpecterPSBT.from_dict(
        {"base64": str(stored.psbt), "recipient_amount_reduced": True}, None, {}
    )
    assert reopened.recipient_amount_reduced is True
