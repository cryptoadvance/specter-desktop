"""Liquid PSET merge regressions: finalized raw txs and sighash handling."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from embit import ec
from embit.liquid.networks import get_network
from embit.liquid.pset import PSET
from embit.liquid.transaction import (
    LTransaction,
    LTransactionInput,
    LTransactionOutput,
    TxInWitness,
)
from embit.psbt import PSBT
from embit.script import Script, Witness
from embit.transaction import SIGHASH, Transaction, TransactionInput, TransactionOutput

from cryptoadvance.specter.liquid.txlist import LTxList
from cryptoadvance.specter.liquid.util.pset import SpecterPSET
from cryptoadvance.specter.util.psbt import SpecterPSBT, witness_items

ASSET = b"\x01" * 32
DEST = Script(b"\x00\x14" + b"\x02" * 20)
CHANGE = Script(b"\x00\x14" + b"\x03" * 20)
NETWORK = get_network("liquidv1")


def bitcoin_pending():
    tx = Transaction(
        vin=[TransactionInput(b"\x01" * 32, 0)],
        vout=[TransactionOutput(900, DEST)],
    )
    psbt = PSBT(tx)
    psbt.inputs[0].witness_utxo = TransactionOutput(1000, CHANGE)
    return SpecterPSBT(psbt, None, None)


def liquid_pending():
    tx = LTransaction(
        vin=[LTransactionInput(b"\x01" * 32, 0)],
        vout=[
            LTransactionOutput(ASSET, 900, DEST),
            LTransactionOutput(ASSET, 100, CHANGE),
        ],
    )
    pset = PSET(tx)
    pset.inputs[0].witness_utxo = LTransactionOutput(ASSET, 1000, CHANGE)
    return SpecterPSET(pset, None, NETWORK)


def test_witness_items_handles_bitcoin_and_liquid_inputs():
    btc_vin = TransactionInput(b"\x01" * 32, 0, witness=Witness([b"sig"]))
    liquid_vin = LTransactionInput(
        b"\x01" * 32, 0, witness=TxInWitness(script_witness=Witness([b"sig"]))
    )
    assert witness_items(btc_vin) == [b"sig"]
    assert witness_items(liquid_vin) == [b"sig"]


def test_liquid_finalized_raw_transaction_with_empty_scriptsig_is_accepted():
    """Elements Core finalizes into TxInWitness, leaving scriptSig empty."""
    psbt = liquid_pending()
    final = LTransaction.parse(psbt.psbt.tx.serialize())
    assert final.vin[0].script_sig.data == b""
    final.vin[0].witness = TxInWitness(script_witness=Witness([b"sig", b"pub"]))
    psbt.update(None, {"hex": final.serialize().hex()})
    assert psbt.raw == final.serialize()


def test_liquid_finalized_raw_transaction_without_witness_is_rejected():
    psbt = liquid_pending()
    final = LTransaction.parse(psbt.psbt.tx.serialize())
    with pytest.raises(ValueError, match="Final transaction"):
        psbt.update(None, {"hex": final.serialize().hex()})
    assert psbt.raw is None


def test_bitcoin_finalized_raw_transaction_with_witness_is_accepted():
    psbt = bitcoin_pending()
    final = Transaction.parse(psbt.psbt.tx.serialize())
    final.vin[0].witness = Witness([b"sig"])
    psbt.update(None, {"hex": final.serialize().hex()})
    assert psbt.raw == final.serialize()


def test_liquid_trusted_merge_keeps_core_filled_utxo():
    psbt = liquid_pending()
    psbt.psbt.inputs[0].witness_utxo = None
    incoming = PSET.parse(psbt.psbt.serialize())
    incoming.inputs[0].witness_utxo = LTransactionOutput(ASSET, 1000, CHANGE)
    psbt.update(str(incoming), trusted=True)
    assert psbt.psbt.inputs[0].utxo.value == 1000


def test_liquid_untrusted_merge_rejects_final_fields():
    psbt = liquid_pending()
    incoming = PSET.parse(psbt.psbt.serialize())
    incoming.inputs[0].final_scriptwitness = Witness([b"sig"])
    with pytest.raises(ValueError, match="final fields"):
        psbt.update(str(incoming))
    assert psbt.psbt.inputs[0].final_scriptwitness is None


def test_liquid_txlist_merges_core_pset_as_trusted(monkeypatch):
    raw_tx = LTransaction.parse(liquid_pending().psbt.tx.serialize())
    core_pset = str(liquid_pending().psbt)
    rpc = Mock()
    rpc.walletprocesspsbt.return_value = {"psbt": core_pset}
    txlist = LTxList.__new__(LTxList)
    txlist.parent = SimpleNamespace(rpc=rpc, descriptor=None, network=NETWORK)
    seen = {}

    def fake_update(self, b64psbt, raw=None, trusted=False):
        seen.update(b64psbt=b64psbt, trusted=trusted)

    monkeypatch.setattr(SpecterPSET, "update", fake_update)
    txlist._get_psbt(raw_tx)
    assert seen == {"b64psbt": core_pset, "trusted": True}


def test_sighash_default_is_zero_in_embit():
    assert SIGHASH.DEFAULT == 0
    assert SIGHASH.ALL == 1


def test_bitcoin_taproot_sighash_default_is_mergeable():
    psbt = bitcoin_pending()
    incoming = PSBT.parse(psbt.psbt.serialize())
    pub = ec.PrivateKey(b"\x01" * 32).get_public_key()
    incoming.inputs[0].sighash_type = SIGHASH.DEFAULT
    incoming.inputs[0].partial_sigs[pub] = b"signature"
    psbt.update(str(incoming))
    assert psbt.psbt.inputs[0].partial_sigs[pub] == b"signature"


def test_liquid_taproot_sighash_default_is_mergeable():
    psbt = liquid_pending()
    incoming = PSET.parse(psbt.psbt.serialize())
    pub = ec.PrivateKey(b"\x01" * 32).get_public_key()
    incoming.inputs[0].sighash_type = SIGHASH.DEFAULT
    incoming.inputs[0].partial_sigs[pub] = b"signature"
    psbt.update(str(incoming))
    assert psbt.psbt.inputs[0].partial_sigs[pub] == b"signature"


@pytest.mark.parametrize("sighash", [2, 3, 0x81])
def test_liquid_merge_rejects_non_default_sighash(sighash):
    psbt = liquid_pending()
    incoming = PSET.parse(psbt.psbt.serialize())
    incoming.inputs[0].sighash_type = sighash
    with pytest.raises(ValueError, match="sighash"):
        psbt.update(str(incoming))
    assert psbt.psbt.inputs[0].sighash_type is None
