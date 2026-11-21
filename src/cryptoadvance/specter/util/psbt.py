"""
The goal of this module is to slowly migrate from json-like representation of PSBT received from Bitcoin RPC
to a normal PSBT class that does not require RPC calls and can do more things.
to_dict and from_dict methods are maintained for backward-compatibility
"""
import logging
from cryptoadvance.specter.key import Key
from embit.psbt import PSBT, InputScope, OutputScope, DerivationPath
from embit.transaction import Transaction, TransactionOutput, TransactionInput, SIGHASH
from embit.liquid.networks import get_network
from embit import bip32
from embit.descriptor import Descriptor
from math import ceil
import time
from typing import Union, Tuple, List

logger = logging.getLogger(__name__)


class AbstractTxContext:
    """Class inherited from this one must have the following properties:
    - self.network : dict with network constants (see embit.networks)
    - self.descriptor : Descriptor class that can check if it owns a PSBT scope or not
    Allows to pass context Wallet -> SpecterPSBT -> SpecterScope -> SpecterTx
    """

    @property
    def network(self) -> dict:
        if hasattr(self, "parent"):
            return self.parent.network
        raise NotImplementedError("Implement this!")

    @property
    def descriptor(self) -> Descriptor:
        if hasattr(self, "parent"):
            return self.parent.descriptor
        raise NotImplementedError("Implement this!")


class SpecterTx(AbstractTxContext):
    TxCls = Transaction

    def __init__(self, parent: AbstractTxContext, tx: Union[Transaction, str, bytes]):
        self.parent = parent
        if isinstance(tx, str):
            tx = self.TxCls.from_string(tx)
        elif isinstance(tx, bytes):
            tx = self.TxCls.parse(tx)
        self.tx = tx

    def vin_to_dict(self, vin: TransactionInput) -> dict:
        return {
            "txid": vin.txid.hex(),
            "vout": vin.vout,
            "sequence": vin.sequence,
        }

    def vout_to_dict(self, vout: TransactionOutput) -> dict:
        i = self.tx.vout.index(vout)
        obj = {
            "value": round(1e-8 * vout.value, 8),
            "sats": vout.value,
            "n": i,
            "scriptPubKey": {
                "hex": vout.script_pubkey.data.hex(),
            },
        }
        try:
            if vout.script_pubkey.data.startswith(b"\x6a"):
                obj["scriptPubKey"]["addresses"] = [
                    "OP_RETURN " + vout.script_pubkey.data.hex()
                ]
            else:
                obj["scriptPubKey"]["addresses"] = [
                    vout.script_pubkey.address(self.network)
                ]
        except:
            pass
        return obj

    def to_dict(self) -> dict:
        if not self.tx:
            return {}
        txid = self.tx.txid().hex()
        size = len(self.tx.serialize())
        return {
            "txid": txid,
            "hash": txid,  # not sure why it's the same
            "version": self.tx.version,
            "size": size,
            "vsize": size,
            "weight": 4 * size,
            "locktime": self.tx.locktime,
            "vin": [self.vin_to_dict(vin) for vin in self.tx.vin],
            "vout": [self.vout_to_dict(vout) for vout in self.tx.vout],
        }


class SpecterScope(AbstractTxContext):
    def __init__(
        self, parent: AbstractTxContext, scope: Union[InputScope, OutputScope]
    ):
        self.parent = parent
        self.scope = scope

    @property
    def is_mine(self) -> bool:
        return self.descriptor.owns(self.scope)

    @property
    def is_change(self) -> bool:
        """Returns True only if the scope belongs to change descriptor (branch 1)"""
        return self.descriptor.branch(1).owns(self.scope)

    @property
    def is_receiving(self) -> bool:
        return self.is_mine and not self.is_change

    @property
    def address(self) -> str:
        try:
            if self.scope.script_pubkey.data.startswith(b"\x6a"):
                return "OP_RETURN " + self.scope.script_pubkey.data.hex()
            else:
                return self.scope.script_pubkey.address(self.network)
        except AttributeError as e:  # 'NoneType' object has no attribute 'data'
            if type(self.scope) != InputScope:  # known issue in this case
                logger.exception()
            return None
        except TypeError:
            # remove this and you get in trouble with tests/test_util_psbt.py
            return None

    @property
    def sat_amount(self) -> int:
        """Implement this!"""
        raise NotImplementedError("Not implemented for this scope")

    @property
    def float_amount(self) -> float:
        return round(self.sat_amount * 1e-8, 8)

    def __repr__(self) -> str:
        if self.is_receiving:
            addr_type = "r"
        elif self.is_change:
            addr_type = "c"
        else:
            addr_type = "u"  # unknown
        return f"{self.__class__.__name__}(float_amount={self.float_amount} mine={self.is_mine} adr={self.address} r/c={addr_type})"

    def to_dict(self) -> dict:
        addr = self.address
        try:
            sats = self.sat_amount
        except:
            sats = None
        obj = {
            "change": self.is_change,
            "is_mine": self.is_mine,
        }
        if addr:
            obj["address"] = addr
        if sats is not None:
            obj.update(
                {
                    "float_amount": round(sats * 1e-8, 8),
                    "sat_amount": sats,
                }
            )
        if self.scope.bip32_derivations:
            obj["bip32_derivs"] = [
                {
                    "pubkey": pub.sec().hex(),
                    "master_fingerprint": der.fingerprint.hex(),
                    "path": bip32.path_to_str(der.derivation),
                }
                for pub, der in self.scope.bip32_derivations.items()
            ]
        if self.scope.taproot_bip32_derivations:
            obj["taproot_bip32_derivs"] = [
                {
                    "pubkey": pub.xonly().hex(),
                    "master_fingerprint": der.fingerprint.hex(),
                    "path": bip32.path_to_str(der.derivation),
                    "leaf_hashes": [leaf.hex() for leaf in leafs],
                }
                for pub, (leafs, der) in self.scope.taproot_bip32_derivations.items()
            ]
        if self.scope.taproot_internal_key:
            obj["taproot_internal_key"] = self.scope.taproot_internal_key.xonly().hex()
        return obj


class SpecterInputScope(SpecterScope):
    TxCls = SpecterTx

    @property
    def inp(self) -> InputScope:
        return self.scope

    @property
    def sat_amount(self) -> int:
        if self.scope.utxo is None:
            # If utxo is not there, then the wallet-api from Core was not able to provide
            # the underlying utxo (as it's not part of the wallet). Therefore not mine
            # Therefore float_amount is 0
            return 0
        return self.scope.utxo.value

    @property
    def txid(self) -> bytes:
        return self.scope.txid

    @property
    def vout(self) -> int:
        return self.scope.vout

    def to_dict(self) -> dict:
        obj = super().to_dict()
        obj.update(
            {
                "txid": self.scope.txid.hex(),
                "vout": self.scope.vout,
            }
        )
        if self.scope.witness_utxo:
            obj["witness_utxo"] = {
                "amount": self.float_amount,
                "sats": self.sat_amount,
                "scriptPubKey": {
                    "hex": self.scope.script_pubkey.data.hex(),
                    "addresses": [self.address],
                },
            }
        else:
            obj["non_witness_utxo"] = self.TxCls(
                self, self.scope.non_witness_utxo
            ).to_dict()
        return obj


class SpecterOutputScope(SpecterScope):
    @property
    def out(self) -> OutputScope:
        return self.scope

    @property
    def sat_amount(self) -> int:
        return self.out.value


def witness_items(vin: TransactionInput) -> list:
    """Script witness stack of a transaction input.

    Bitcoin keeps it directly in vin.witness, Liquid wraps it in a TxInWitness
    together with the amount, token and pegin proofs.
    """
    witness = vin.witness
    if hasattr(witness, "script_witness"):
        witness = witness.script_witness
    return witness.items


def unsigned_transaction_bytes(psbt: PSBT) -> bytes:
    """Compare on-chain output commitments, not PSET-only unblinded metadata."""
    tx = psbt.tx
    tx.vout = [
        scope.blinded_vout if hasattr(scope, "blinded_vout") else scope.vout
        for scope in psbt.outputs
    ]
    return tx.serialize()


class SpecterPSBT(AbstractTxContext):
    """Specter's PSBT class with some handy functions"""

    PSBTCls = PSBT
    InputCls = SpecterInputScope
    OutputCls = SpecterOutputScope
    TxCls = SpecterTx

    def __init__(
        self,
        psbt: Union[str, PSBT],
        descriptor: Descriptor,
        network: dict,
        raw: Union[None, str] = None,
        devices: List[Tuple[Key, str]] = [],  # list of tuples: (Key, device_alias)
        **kwargs,
    ):
        """
        kwargs can contain:
        - "time" - creation time of the transaction, time.time() is used if missing,
        - other keys in kwargs are dropped
        """
        if isinstance(psbt, str):
            psbt = self.PSBTCls.from_string(psbt)
        self.psbt: PSBT = psbt
        self._descriptor = descriptor
        self._network = network
        self.devices = devices
        self.raw = bytes.fromhex(raw) if raw else None
        self.time = kwargs.get("time", time.time())
        self.recipient_amount_reduced = kwargs.get("recipient_amount_reduced", False)

    @property
    def network(self) -> dict:
        return self._network

    @property
    def descriptor(self) -> Descriptor:
        return self._descriptor

    def update(self, b64psbt: str, raw: dict = None, trusted: bool = False) -> None:
        """Merge only signatures and key origins for the same unsigned transaction.

        b64psbt - PSBT transaction with some extra data that we should take
        raw dict can contain "hex" key with hex string of the finalized transaction. Or not.
        trusted - only for PSBTs coming from the local Core wallet, which also fills
        UTXO data and final fields of transactions already in the wallet history.
        A finalized raw transaction may have a different txid due to scriptSig;
        compare its unsigned fields instead of its txid.
        """
        psbt = self.PSBTCls.from_string(b64psbt) if b64psbt else None
        if psbt:
            if unsigned_transaction_bytes(psbt) != unsigned_transaction_bytes(
                self.psbt
            ):
                raise ValueError(
                    "PSBT unsigned transaction does not match pending transaction"
                )
            if not trusted:
                for inp in psbt.inputs:
                    # SIGHASH_DEFAULT (0) is what taproot signers use and embit
                    # signs non-taproot inputs with SIGHASH_ALL in that case.
                    if inp.sighash_type not in (
                        None,
                        SIGHASH.DEFAULT,
                        SIGHASH.ALL,
                    ):
                        raise ValueError("Unsupported PSBT sighash type")
                    if (
                        inp.final_scriptsig is not None
                        or inp.final_scriptwitness is not None
                    ) and not (raw and "hex" in raw):
                        raise ValueError("Cannot merge unverified PSBT final fields")

        finalized = None
        if raw and "hex" in raw:
            finalized = bytes.fromhex(raw["hex"])
            tx = self.TxCls.TxCls.parse(finalized)
            unsigned = self.psbt.tx
            if (
                tx.version != unsigned.version
                or tx.locktime != unsigned.locktime
                or len(tx.vin) != len(unsigned.vin)
                or len(tx.vout) != len(unsigned.vout)
                or any(
                    vin.txid != original.txid
                    or vin.vout != original.vout
                    or vin.sequence != original.sequence
                    or not (vin.script_sig.data or witness_items(vin))
                    for vin, original in zip(tx.vin, unsigned.vin)
                )
                or any(
                    out.serialize()
                    != (
                        scope.blinded_vout
                        if hasattr(scope, "blinded_vout")
                        else scope.vout
                    ).serialize()
                    for out, scope in zip(tx.vout, self.psbt.outputs)
                )
            ):
                raise ValueError("Final transaction does not match pending transaction")

        if psbt:
            for dest, source in zip(self.psbt.inputs, psbt.inputs):
                if trusted:
                    # Core fills UTXOs and scripts for transaction history.
                    dest.update(source)
                else:
                    dest.partial_sigs.update(source.partial_sigs)
                    dest.bip32_derivations.update(source.bip32_derivations)
                    dest.taproot_bip32_derivations.update(
                        source.taproot_bip32_derivations
                    )
                    # embit 0.6.1 has no taproot_sigs scope attribute.
                    if hasattr(dest, "taproot_sigs") and hasattr(
                        source, "taproot_sigs"
                    ):
                        dest.taproot_sigs.update(source.taproot_sigs)
                    self._merge_unknown(dest, source)
            for dest, source in zip(self.psbt.outputs, psbt.outputs):
                if trusted:
                    dest.update(source)
                else:
                    dest.bip32_derivations.update(source.bip32_derivations)
                    dest.taproot_bip32_derivations.update(
                        source.taproot_bip32_derivations
                    )
        if finalized is not None:
            self.raw = finalized

    # embit 0.6.1 keeps BIP-371 signature fields in input.unknown.
    TAPROOT_KEY_SIG_KEY = b"\x13"
    TAPROOT_SCRIPT_SIG_PREFIX = 0x14
    TAPROOT_SCRIPT_SIG_KEY_LENGTH = 65  # type + xonly pubkey + leaf hash

    @classmethod
    def _mergeable_unknown(cls, key: bytes, value: bytes) -> bool:
        """Allow only well-sized taproot signature fields from external signers."""
        if not isinstance(key, bytes) or not isinstance(value, bytes):
            return False
        if key == cls.TAPROOT_KEY_SIG_KEY:
            return len(value) in (64, 65)
        if (
            len(key) == cls.TAPROOT_SCRIPT_SIG_KEY_LENGTH
            and key[0] == cls.TAPROOT_SCRIPT_SIG_PREFIX
        ):
            return len(value) in (64, 65)
        return False

    @classmethod
    def _merge_unknown(cls, dest, source) -> None:
        """Keep existing signatures; copy allowed entries to the same input."""
        for key, value in source.unknown.items():
            if key not in dest.unknown and cls._mergeable_unknown(key, value):
                dest.unknown[key] = value

    def utxo_dict(self) -> dict:
        return [{"txid": inp.txid.hex(), "vout": inp.vout} for inp in self.psbt.inputs]

    @property
    def extra_input_weight(self) -> int:
        redeem_script = self.descriptor.redeem_script()
        witness_script = self.descriptor.witness_script()
        weight = 0
        if redeem_script:
            weight += len(redeem_script.data) * 4
        if witness_script:
            weight += (
                len(witness_script.data) + 2
            )  # number of items in witness + script length
            if self.descriptor.is_basic_multisig:
                threshold = self.descriptor.miniscript.args[0].num
                num_keys = len(self.descriptor.keys)
                weight += num_keys * 34
                weight += threshold * 75
        else:
            # pubkey, signature
            weight += 75 + 34
        return weight

    @property
    def full_size(self) -> int:
        weight = len(self.psbt.tx.serialize()) * 4 + 4  # marker will be added
        weight += len(self.inputs) * self.extra_input_weight
        return ceil(weight / 4)

    @property
    def fee(self) -> int:
        return self.psbt.fee()

    @property
    def fee_rate(self) -> float:
        return self.fee / self.full_size

    @property
    def threshold(self) -> int:
        if self.descriptor.is_basic_multisig:
            return self.descriptor.miniscript.args[0].num
        return 1

    @property
    def sigs_count(self) -> int:
        # everything is signed if final witness is there or
        if self.raw or any([inp.final_scriptwitness for inp in self.psbt.inputs]):
            return self.threshold
        # not quite true but ok for most common cases
        return max([len(inp.partial_sigs) for inp in self.psbt.inputs])

    def should_display(self, out: SpecterOutputScope) -> bool:
        """Checks if this output should be displayed"""
        return not self.descriptor.branch(1).owns(out.scope)

    @property
    def addresses(self) -> List[str]:
        return [out.address for out in self.outputs if self.should_display(out)]

    @property
    def amounts(self) -> List[float]:
        return [out.float_amount for out in self.outputs if self.should_display(out)]

    @property
    def sats(self) -> List[int]:
        return [out.value for out in self.psbt.outputs if not self.descriptor.owns(out)]

    @property
    def txid(self) -> str:
        return self.psbt.tx.txid().hex()

    @property
    def inputs(self) -> List[SpecterInputScope]:
        return [self.InputCls(self, inp) for inp in self.psbt.inputs]

    @property
    def outputs(self) -> List[SpecterOutputScope]:
        return [self.OutputCls(self, out) for out in self.psbt.outputs]

    @property
    def tx(self) -> Transaction:
        return self.TxCls(self, self.psbt.tx)

    def get_signed_devices(self) -> List[str]:
        if not self.devices:
            return []
        devices = []
        # for each devices check if there is a partial signature for any input
        for key, device in self.devices:
            device_signed = False
            for inp in self.psbt.inputs:
                if not inp.partial_sigs:
                    continue
                for pub in inp.partial_sigs:
                    der = inp.bip32_derivations.get(pub)
                    if der and der.fingerprint.hex() == key.fingerprint:
                        device_signed = True
                        break
                if device_signed:
                    break
            if device_signed and device not in devices:
                devices.append(device)
        return devices

    @classmethod
    def from_dict(cls, obj: dict, descriptor: Descriptor, network: dict, devices=[]):
        psbt = cls.PSBTCls.from_string(obj["base64"])
        kwargs = {}
        kwargs.update(obj)
        kwargs.pop("base64")
        return cls(psbt, descriptor, network, devices=devices, **kwargs)

    @classmethod
    def from_transaction(
        cls,
        tx: Union[Transaction, str, bytes],
        descriptor: Descriptor,
        network: dict,
        devices=[],
    ):
        if isinstance(tx, str):
            tx = cls.TxCls.from_string(tx)
        elif isinstance(tx, bytes):
            tx = cls.TxCls.parse(tx)
        psbt = cls.PSBTCls(tx)
        return cls(psbt, descriptor, network, devices=devices)

    def to_dict(self) -> dict:
        # fee calculation may fail if inputs info is missing
        try:
            fee = self.fee
        except:
            fee = 0
        full_size = self.full_size
        obj = {
            "tx": self.tx.to_dict(),
            "inputs": [inp.to_dict() for inp in self.inputs],
            "outputs": [out.to_dict() for out in self.outputs],
            "base64": str(self.psbt),
            "fee": round(fee * 1e-8, 8),
            "fee_sat": fee,
            "address": self.addresses,
            "amount": self.amounts,
            "sats": self.sats,
            "tx_full_size": full_size,
            "sigs_count": self.sigs_count,
            "time": self.time,
            "devices_signed": [
                device if isinstance(device, str) else device.alias
                for device in self.get_signed_devices()
            ],
            "fee_rate": round(fee / full_size, 2),
        }
        if self.recipient_amount_reduced:
            obj["recipient_amount_reduced"] = True
        if self.raw:
            obj.update({"raw": self.raw.hex()})
        return obj

    @classmethod
    def from_string(cls, b64psbt: str) -> PSBT:
        """Returns PSBTCls, not cls"""
        return cls.PSBTCls.from_string(b64psbt)

    def to_string(self) -> str:
        return str(self.psbt)

    def __str__(self):
        return str(self.psbt)

    @classmethod
    def fill_output(cls, out: OutputScope, desc: Descriptor) -> bool:
        """
        Fills derivations and all other information in PSBT output
        from derived descriptor
        """
        if desc.script_pubkey() != out.script_pubkey:
            return False
        out.redeem_script = desc.redeem_script()
        out.witness_script = desc.witness_script()
        out.bip32_derivations = {
            key.get_public_key(): DerivationPath(
                key.origin.fingerprint, key.origin.derivation
            )
            for key in desc.keys
        }
        return True
