"""Node-free evidence that fee handling matches the requested rate.

PR #2744 removed a second ``walletcreatefundedpsbt`` pass that re-scaled
``options["feeRate"]`` by ``fee_rate / psbt.fee_rate``. No bitcoind is
available in this environment, so the RPC stub below models Core's documented
funding contract instead of talking to a node: it funds the transaction once at
``options["feeRate"]`` and derives the fee from a signed-size estimate built
from maximum-size ECDSA signatures plus the descriptor's witness/redeem script.

The assertions then measure the fee rate of the transaction as it would
serialize once every input carries its signatures, which is the number that
decides whether the transaction relays. A second test replays the deleted
formula to show that it misses the requested rate, and the RBF tests cover the
``change_index`` handling guarded by the same PR.
"""

from math import ceil
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from embit import bip32, networks
from embit.descriptor import Descriptor
from embit.psbt import PSBT, DerivationPath
from embit.script import Script, Witness, address_to_scriptpubkey
from embit.transaction import Transaction, TransactionInput, TransactionOutput

from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.util.psbt import SpecterPSBT
from cryptoadvance.specter.wallet.wallet import Wallet

FEE_RATE = 10.0  # sat/vB requested by the user
# The repository compares fee rates with a 1% tolerance (tests/test_rest.py).
TOLERANCE = 0.01
RECIPIENT = "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
THRESHOLD = 2
UTXO_SATS = 1_000_000

KEYS = [
    bip32.HDKey.from_seed(seed).to_public().to_base58()
    for seed in (b"specter-multisig-1", b"specter-multisig-2", b"specter-multisig-3")
]

DESCRIPTORS = {
    "wsh": "wsh(sortedmulti(%d,%s/{0,1}/*,%s/{0,1}/*,%s/{0,1}/*))",
    "sh-wsh": "sh(wsh(sortedmulti(%d,%s/{0,1}/*,%s/{0,1}/*,%s/{0,1}/*)))",
    "sh": "sh(sortedmulti(%d,%s/{0,1}/*,%s/{0,1}/*,%s/{0,1}/*))",
}


def descriptor_for(kind):
    return Descriptor.from_string(DESCRIPTORS[kind] % (THRESHOLD, *KEYS))


def push(data):
    """Minimal script push so a legacy scriptSig can be measured exactly."""
    if len(data) < 0x4C:
        return bytes([len(data)]) + data
    if len(data) <= 0xFF:
        return b"\x4c" + bytes([len(data)]) + data
    return b"\x4d" + len(data).to_bytes(2, "little") + data


def max_signature():
    """Largest DER-encoded ECDSA signature (72 bytes) plus its sighash byte."""
    return b"\x30" * 72 + b"\x01"


def fully_signed_vsize(tx, descriptor):
    """vsize of ``tx`` once each input carries THRESHOLD maximum-size signatures."""
    signed = Transaction.parse(tx.serialize())
    witness_script = descriptor.witness_script()
    redeem_script = descriptor.redeem_script()
    sigs = [max_signature()] * THRESHOLD
    for vin in signed.vin:
        if witness_script is None:  # legacy P2SH multisig: sigs live in the scriptSig
            vin.script_sig = Script(
                b"\x00" + b"".join(push(sig) for sig in sigs) + push(redeem_script.data)
            )
        elif redeem_script is not None:  # sh(wsh(...)): scriptSig holds the p2wsh hash
            vin.script_sig = Script(push(redeem_script.data))
    base_size = len(signed.serialize())  # still without witnesses
    witness_size = 0
    if witness_script is not None:
        for vin in signed.vin:
            vin.witness = Witness([b""] + sigs + [witness_script.data])
            witness_size += len(vin.witness.serialize())
    if witness_size:
        return ceil((base_size * 4 + witness_size) / 4)
    return base_size


class CoreLikeRpc:
    """Stands in for Core's wallet RPC; funds once at options["feeRate"]."""

    def __init__(self, descriptor, utxo_sats=UTXO_SATS):
        self.descriptor = descriptor
        self.utxo_sats = utxo_sats
        self.utxo_txid = "11" * 32
        self.calls = []

    def getchaintips(self):
        return [{"height": 800000}]

    def listunspent(self, *args):
        return []

    def walletcreatefundedpsbt(self, inputs, outputs, locktime, options, bip32derivs):
        self.calls.append(
            {
                "inputs": inputs,
                "outputs": outputs,
                "locktime": locktime,
                "options": dict(options),
                "bip32derivs": bip32derivs,
            }
        )
        fee_rate = options["feeRate"] * 1e8 / 1000  # BTC/kB -> sat/vB
        recipient_address, recipient_btc = next(iter(outputs[0].items()))
        recipient_sats = round(recipient_btc * 1e8)
        change_script = self.descriptor.branch(1).derive(0).script_pubkey()
        tx = Transaction(
            vin=[TransactionInput(bytes.fromhex(self.utxo_txid), 0)],
            vout=[
                TransactionOutput(
                    recipient_sats, address_to_scriptpubkey(recipient_address)
                ),
                TransactionOutput(0, change_script),
            ],
        )
        fee = ceil(fee_rate * fully_signed_vsize(tx, self.descriptor))
        change_sats = self.utxo_sats - recipient_sats - fee
        assert change_sats > 546, "stub refuses to create dust change"
        tx.vout[1].value = change_sats

        psbt = PSBT(tx)
        psbt.inputs[0].witness_utxo = TransactionOutput(
            self.utxo_sats, self.descriptor.branch(0).derive(0).script_pubkey()
        )
        if bip32derivs:
            self._fill_derivations(psbt)
        return {"psbt": str(psbt)}

    def _fill_derivations(self, psbt):
        """Core fills bip32 derivations, which is how Specter spots change."""
        fingerprint = self.descriptor.keys[0].my_fingerprint
        received = self.descriptor.derive(0, branch_index=0)
        psbt.inputs[0].bip32_derivations[received.keys[0].get_public_key()] = (
            DerivationPath(fingerprint, [0, 0])
        )
        change = self.descriptor.derive(0, branch_index=1)
        psbt.outputs[1].bip32_derivations[change.keys[0].get_public_key()] = (
            DerivationPath(fingerprint, [1, 0])
        )


class NodeFreeWallet(Wallet):
    """Watch-only wallet whose balance and Core RPC are supplied by the test."""

    @property
    def amount_available(self):
        return self._available


def make_wallet(descriptor, rpc):
    wallet = NodeFreeWallet.__new__(NodeFreeWallet)
    wallet._available = 1.0
    wallet.alias = "watch-only-multisig"
    wallet._rpc = rpc
    wallet.manager_rpc = rpc
    wallet.manager = SimpleNamespace(
        rpc=rpc, rpc_path="wallets", bitcoin_core_version_raw=210000, chain="main"
    )
    wallet.descriptor = descriptor
    wallet.keys = []
    wallet._devices = []
    wallet.change_index = 0
    wallet.change_address = (
        descriptor.branch(1).derive(0).address(networks.NETWORKS["main"])
    )
    wallet.balance = {"trusted": 1.0, "untrusted_pending": 0.0, "immature": 0.0}
    wallet.PSBTCls = SpecterPSBT
    wallet.save_pending_psbt = Mock()
    wallet.fill_psbt = lambda b64psbt: b64psbt
    return wallet


def funded_psbt(kind, fee_rate=FEE_RATE):
    descriptor = descriptor_for(kind)
    rpc = CoreLikeRpc(descriptor)
    wallet = make_wallet(descriptor, rpc)
    psbt = wallet.createpsbt(
        [RECIPIENT], [0.005], fee_rate=fee_rate, rbf_edit_mode=True
    )
    return descriptor, rpc, wallet, psbt


@pytest.mark.parametrize("kind", list(DESCRIPTORS))
def test_watch_only_multisig_pays_requested_fee_rate(kind):
    """2-of-3 watch-only descriptor wallet: requested 10 sat/vB == actual."""
    descriptor, rpc, wallet, psbt = funded_psbt(kind)

    # One funding call, at exactly the requested rate (10 sat/vB -> BTC/kB).
    assert len(rpc.calls) == 1
    assert rpc.calls[0]["options"]["feeRate"] == pytest.approx(0.0001, rel=1e-9)

    actual_vsize = fully_signed_vsize(psbt.psbt.tx, descriptor)
    actual_fee_rate = psbt.fee / actual_vsize
    assert actual_fee_rate == pytest.approx(
        FEE_RATE, rel=TOLERANCE
    ), f"{kind} multisig paid {actual_fee_rate:.2f} sat/vB for {FEE_RATE} requested"
    wallet.save_pending_psbt.assert_called_once_with(psbt)


@pytest.mark.parametrize("kind", list(DESCRIPTORS))
def test_removed_second_pass_would_miss_the_requested_rate(kind):
    """Replays the deleted lines: they change the rate Core is asked to fund."""
    descriptor, rpc, wallet, psbt = funded_psbt(kind)
    assert len(rpc.calls) == 1

    # Deleted code: scale = fee_rate / psbt.fee_rate; adjusted = fee_rate * scale
    adjusted_fee_rate = FEE_RATE * (FEE_RATE / psbt.fee_rate)
    assert adjusted_fee_rate != pytest.approx(FEE_RATE, rel=TOLERANCE)

    replay_rpc = CoreLikeRpc(descriptor)
    replay_wallet = make_wallet(descriptor, replay_rpc)
    replayed = replay_wallet.createpsbt(
        [RECIPIENT], [0.005], fee_rate=adjusted_fee_rate, rbf_edit_mode=True
    )
    replayed_rate = replayed.fee / fully_signed_vsize(replayed.psbt.tx, descriptor)
    assert replayed_rate != pytest.approx(FEE_RATE, rel=TOLERANCE)


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
    wallet = make_wallet(descriptor_for("wsh"), Mock())
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
    wallet.save_pending_psbt.assert_not_called()
