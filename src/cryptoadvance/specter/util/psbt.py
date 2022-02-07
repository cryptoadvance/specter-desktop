"""
The goal of this module is to slowly migrate from json-like representation of PSBT received from Bitcoin RPC
to a normal PSBT class that does not require RPC calls and can do more things.
to_dict and from_dict methods are maintained for backward-compatibility
"""
from cryptoadvance.specter.key import Key
from embit.psbt import PSBT, InputScope, OutputScope, DerivationPath
from embit.transaction import Transaction, TransactionOutput, TransactionInput
from embit.liquid.networks import get_network
from embit import bip32
from embit.descriptor import Descriptor
from math import ceil
import time
from typing import Union, Tuple, List


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
            if scope.script_pubkey.data.startswith(b"\x6a"):
                obj["scriptPubKey"]["addresses"] = [
                    "OP_RETURN " + scope.script_pubkey.data.hex()
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
        except:
            return None

    @property
    def sat_amount(self) -> int:
        """Implement this!"""
        raise NotImplementedError("Not implemented for this scope")

    @property
    def float_amount(self) -> float:
        return round(self.sat_amount * 1e-8, 8)

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
        return obj


class SpecterInputScope(SpecterScope):
    TxCls = SpecterTx

    @property
    def inp(self) -> InputScope:
        return self.scope

    @property
    def sat_amount(self) -> int:
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
        **kwargs
    ):
        """
        kwargs can contain:
        - "time" - creation time of the transaction, time.time() is used if missing,
        - other keys in kwargs are dropped
        """
        if isinstance(psbt, str):
            psbt = self.PSBTCls.from_string(psbt)
        self.psbt = psbt
        self._descriptor = descriptor
        self._network = network
        self.devices = devices
        self.raw = bytes.fromhex(raw) if raw else None
        self.time = kwargs.get("time", time.time())

    @property
    def network(self) -> dict:
        return self._network

    @property
    def descriptor(self) -> Descriptor:
        return self._descriptor

    def update(self, b64psbt: str, raw: dict = {}) -> None:
        """
        b64psbt - PSBT transaction with some extra data that we should take
        raw dict can contain "hex" key with hex string of the finalized transaction. Or not.
        """
        if raw and "hex" in raw:
            self.raw = bytes.fromhex(raw["hex"])
        if not b64psbt:
            return
        psbt = self.PSBTCls.from_string(b64psbt)
        for inp1, inp2 in zip(self.psbt.inputs, psbt.inputs):
            inp1.update(inp2)
        for out1, out2 in zip(self.psbt.outputs, psbt.outputs):
            out1.update(out2)

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
