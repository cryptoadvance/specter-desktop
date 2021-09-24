"""
The goal of this module is to slowly migrate from json-like representation of PSBT received from Bitcoin RPC
to a normal PSBT class that does not require RPC calls and can do more things.
to_dict and from_dict methods are maintained for backward-compatibility
"""
from embit.psbt import PSBT, InputScope, OutputScope
from embit.transaction import Transaction, TransactionOutput
from embit.liquid.networks import get_network
from embit import bip32
from math import ceil
import time


class SpecterTx:
    def __init__(self, parent, tx):
        self.parent = parent
        self.tx = tx

    @property
    def network(self):
        return self.parent.network

    def vin_to_dict(self, vin):
        return {
            "txid": vin.txid.hex(),
            "vout": vin.vout,
            "sequence": vin.sequence,
        }

    def vout_to_dict(self, vout):
        i = self.tx.vout.index(vout)
        return {
            "value": round(1e-8 * vout.value, 8),
            "sats": vout.value,
            "n": i,
            "scriptPubKey": {
                "hex": vout.script_pubkey.data.hex(),
                "addresses": [vout.script_pubkey.address(self.network)],
            },
        }

    def to_dict(self):
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
            "vin": [
                self.vin_to_dict(vin)
                for vin in self.tx.vin
            ],
            "vout": [
                self.vout_to_dict(vout)
                for vout in self.tx.vout
            ],
        }


class SpecterScope:
    def __init__(self, parent, scope):
        self.parent = parent
        self.scope = scope

    @property
    def network(self):
        return self.parent.network

    @property
    def descriptor(self):
        return self.parent.descriptor

    @property
    def is_mine(self):
        return self.descriptor.owns(self.scope)

    @property
    def is_change(self):
        return self.descriptor.branch(1).owns(self.scope)

    @property
    def is_receiving(self):
        return self.is_mine and not self.is_change

    @property
    def address(self):
        return self.scope.script_pubkey.address(self.network)

    @property
    def sat_amount(self):
        """Implement this!"""
        raise NotImplementedError("Not implemented for this scope")

    @property
    def float_amount(self):
        return round(self.sat_amount * 1e-8, 8)

    def to_dict(self):
        obj = {
            "address": self.address,
            "float_amount": self.float_amount,
            "sat_amount": self.sat_amount,
            "change": self.is_change,
            "is_mine": self.is_mine,
        }
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
    def inp(self):
        return self.scope

    @property
    def sat_amount(self):
        return self.scope.utxo.value

    @property
    def txid(self):
        return self.scope.txid

    @property
    def vout(self):
        return self.scope.vout

    def to_dict(self):
        obj = super().to_dict()
        obj.update({
            "txid": self.scope.txid.hex(),
            "vout": self.scope.vout,
        })
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
            obj["non_witness_utxo"] = self.TxCls(self, self.scope.non_witness_utxo)
        return obj


class SpecterOutputScope(SpecterScope):

    @property
    def out(self):
        return self.scope

    @property
    def sat_amount(self):
        return self.out.value


class SpecterPSBT:
    """Specter's PSBT class with some handy functions"""
    PSBTCls = PSBT
    InputCls = SpecterInputScope
    OutputCls = SpecterOutputScope
    TxCls = SpecterTx

    def __init__(self,
        psbt,
        descriptor,
        network,
        **kwargs
    ):
        if isinstance(psbt, str):
            psbt = self.PSBTCls.from_string(psbt)
        self.psbt = psbt
        self.descriptor = descriptor
        self.network = network
        self.time = kwargs.get("time", time.time())
        self.devices = kwargs.get("devices", [])

    def utxo_dict(self):
        return [{"txid": inp.txid.hex(), "vout": inp.vout} for inp in self.psbt.inputs]

    @property
    def extra_input_weight(self):
        redeem_script = self.descriptor.redeem_script()
        witness_script = self.descriptor.witness_script()
        weight = 0
        if redeem_script:
            weight += len(redeem_script.data) * 4
        if witness_script:
            weight += len(witness_script.data)
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
    def full_size(self):
        size = len(self.psbt.tx.serialize()) * 4
        size += len(self.inputs) * self.extra_input_weight
        return ceil(size / 4)

    @property
    def sigs_count(self):
        # not quite true but ok for most cases
        return max([len(inp.partial_sigs) for inp in self.psbt.inputs])

    @property
    def addresses(self):
        return [
            out.script_pubkey.address(self.network)
            for out in self.psbt.outputs
            if not self.descriptor.owns(out)
        ]

    @property
    def amounts(self):
        return [
            round(out.value * 1e-8, 8)
            for out in self.psbt.outputs
            if not self.descriptor.owns(out)
        ]

    @property
    def sats(self):
        return [out.value for out in self.psbt.outputs if not self.descriptor.owns(out)]

    @property
    def txid(self):
        return self.psbt.tx.txid().hex()

    def fee(self):
        return self.psbt.fee()

    @property
    def inputs(self):
        return [self.InputCls(self, inp) for inp in self.psbt.inputs]

    @property
    def outputs(self):
        return [self.OutputCls(self, out) for out in self.psbt.outputs]

    @property
    def tx(self):
        return self.TxCls(self, self.psbt.tx)

    @classmethod
    def from_dict(cls, obj, descriptor, chain):
        psbt = cls.PSBTCls.from_string(obj["base64"])
        network = get_network(chain)
        kwargs = {}
        kwargs.update(obj)
        kwargs.pop("base64")
        return cls(psbt, descriptor, network, **kwargs)

    def to_dict(self):
        return {
            "tx": self.tx.to_dict(),
            "inputs": [inp.to_dict() for inp in self.inputs],
            "outputs": [out.to_dict() for out in self.outputs],
            "base64": str(self.psbt),
            "fee": round(self.fee() * 1e-8, 8),
            "fee_sat": self.fee(),
            "address": self.addresses,
            "amount": self.amounts,
            "sats": self.sats,
            "tx_full_size": self.full_size,
            "sigs_count": self.sigs_count,
            "time": self.time,
        }

    @classmethod
    def from_string(cls, b64psbt):
        """Returns PSBTCls, not cls"""
        return cls.PSBTCls.from_string(b64psbt)

    def to_string(self):
        return str(self.psbt)