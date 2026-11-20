"""Jade signing protocol regression without a physical device or node fixtures."""

from pathlib import Path
from unittest.mock import Mock

from hwilib.common import Chain
from hwilib.psbt import PSBT

from cryptoadvance.specter.devices.hwi.jade import JadeClient

PSBT_FIXTURE = Path(__file__).parent / "fixtures" / "jade_hardware.psbt"


def test_jade_sign_tx_uses_plain_signatures_without_ae_parameters():
    psbt = PSBT()
    psbt.deserialize(PSBT_FIXTURE.read_text().strip())
    pubkey, origin = next(iter(psbt.inputs[0].hd_keypaths.items()))
    signature = bytes.fromhex("300602010102010101")

    client = object.__new__(JadeClient)
    client.chain = Chain.TEST
    client.expert = True  # No optional change detection; focus on input signing.
    client.get_master_fingerprint = Mock(return_value=origin.fingerprint)
    client.jade = Mock()
    client.jade.sign_tx.return_value = [signature]

    assert client.sign_tx(psbt) is psbt
    assert psbt.inputs[0].partial_sigs[pubkey] == signature
    client.jade.sign_tx.assert_called_once()
    network, txn, inputs, change = client.jade.sign_tx.call_args.args
    assert network == "testnet"
    assert txn == psbt.get_unsigned_tx().serialize_without_witness()
    assert len(inputs) == 1
    assert inputs[0]["path"] == origin.path
    assert inputs[0]["input_tx"] is not None
    assert "ae_host_entropy" not in inputs[0]
    assert "ae_host_commitment" not in inputs[0]
    assert change == [None] * len(psbt.outputs)
    assert client.jade.sign_tx.call_args.kwargs == {"use_ae_signatures": False}
