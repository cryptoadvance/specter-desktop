"""
The goal of this module is to slowly migrate from json-like representation of PSBT received from Bitcoin RPC
to a normal PSBT class that does not require RPC calls and can do more things.
to_dict and from_dict methods are maintained for backward-compatibility
"""
from embit.psbt import PSBT, InputScope, OutputScope
from embit.transaction import Transaction, TransactionOutput
from embit.networks import NETWORKS
from embit import bip32
from math import ceil
import time


class SpecterTx(Transaction):
    def to_dict(self, network):
        txid = self.txid().hex()
        size = len(self.serialize())
        return {
            "txid": txid,
            "hash": txid,  # not sure why it's the same
            "version": self.version,
            "size": size,
            "vsize": size,
            "weight": 4 * size,
            "locktime": self.locktime,
            "vin": [
                {
                    "txid": vin.txid.hex(),
                    "vout": vin.vout,
                    "sequence": vin.sequence,
                }
                for vin in self.vin
            ],
            "vout": [
                {
                    "value": round(1e-8 * vout.value, 8),
                    "sats": vout.value,
                    "n": i,
                    "scriptPubKey": {
                        "hex": vout.script_pubkey.data.hex(),
                        "addresses": [vout.script_pubkey.address(network)],
                    },
                }
                for i, vout in enumerate(self.vout)
            ],
        }


class SpecterTxOut(TransactionOutput):
    def to_dict(self, network):
        return {
            "amount": round(self.value * 1e-8, 8),
            "sats": self.value,
            "scriptPubKey": {
                "hex": self.script_pubkey.data.hex(),
                "addresses": [self.script_pubkey.address(network)],
            },
        }


class SpecterInputScope(InputScope):
    TX_CLS = SpecterTx
    TXOUT_CLS = SpecterTxOut

    def __init__(self, *args, **kwargs):
        self.parent = None
        super().__init__(*args, **kwargs)

    @property
    def network(self):
        if self.parent:
            return self.parent.network
        return NETWORKS["main"]

    @property
    def address(self):
        return self.script_pubkey.address(self.network)

    @property
    def float_amount(self):
        return round(self.utxo.value * 1e-8, 8)

    @property
    def sat_amount(self):
        return self.utxo.value

    def to_dict(self, network=None):
        network = network or self.network
        obj = {
            "address": self.address,
            "float_amount": self.float_amount,
            "sat_amount": self.utxo.value,
            "txid": self.txid.hex(),
            "vout": self.vout,
        }
        if self.witness_utxo:
            obj["witness_utxo"] = self.witness_utxo.to_dict(network)
        else:
            obj["non_witness_utxo"] = self.non_witness_utxo.to_dict(network)
        if self.bip32_derivations:
            obj["bip32_derivs"] = [
                {
                    "pubkey": pub.sec().hex(),
                    "master_fingerprint": der.fingerprint.hex(),
                    "path": bip32.path_to_str(der.derivation),
                }
                for pub, der in self.bip32_derivations.items()
            ]
        return obj


class SpecterOutputScope(OutputScope):
    def __init__(self, *args, **kwargs):
        self.parent = None
        super().__init__(*args, **kwargs)

    @property
    def network(self):
        if self.parent:
            return self.parent.network
        return NETWORKS["main"]

    @property
    def descriptor(self):
        if self.parent:
            return self.parent.descriptor
        return None

    @property
    def is_change(self):
        if self.descriptor:
            return self.descriptor.branch(1).owns(self)
        return False

    @property
    def is_mine(self):
        if self.descriptor:
            return self.descriptor.owns(self)
        return False

    @property
    def address(self):
        return self.script_pubkey.address(self.network)

    @property
    def float_amount(self):
        return round(self.value * 1e-8, 8)

    @property
    def sat_amount(self):
        return self.value

    def to_dict(self, network):
        network = network or self.network
        obj = {
            "address": self.address,
            "float_amount": self.float_amount,
            "sat_amount": self.value,
            "change": self.is_change,
            "is_mine": self.is_mine,
        }
        if self.bip32_derivations:
            obj["bip32_derivs"] = [
                {
                    "pubkey": pub.sec().hex(),
                    "master_fingerprint": der.fingerprint.hex(),
                    "path": bip32.path_to_str(der.derivation),
                }
                for pub, der in self.bip32_derivations.items()
            ]
        return obj


class SpecterPSBT(PSBT):
    """Specter's PSBT class with some handy functions"""

    PSBTIN_CLS = SpecterInputScope
    PSBTOUT_CLS = SpecterOutputScope
    TX_CLS = SpecterTx

    def __init__(self, *args, **kwargs):
        self.descriptor = None
        self.network = NETWORKS["main"]
        if "descriptor" in kwargs:
            self.descriptor = kwargs.pop("descriptor")
        if "network" in kwargs:
            self.network = kwargs.pop("network")
        self.time = time.time()
        if "time" in kwargs:
            self.time = kwargs.pop("time")
        self.signed_devices = []
        super().__init__(*args, **kwargs)

    @classmethod
    def from_string(cls, *args, **kwargs):
        psbt = super(cls, cls).from_string(*args, **kwargs)
        # set parent to self so we know about descriptor and network
        for sc in psbt.inputs + psbt.outputs:
            sc.parent = psbt
        return psbt

    def utxo_dict(self):
        return [{"txid": inp.txid.hex(), "vout": inp.vout} for inp in self.inputs]

    @classmethod
    def from_dict(cls, obj, descriptor, chain):
        psbt = cls.from_string(obj["base64"])
        psbt.descriptor = descriptor
        psbt.network = NETWORKS.get(chain, NETWORKS["main"])
        psbt.time = obj.get("time", time.time())
        return psbt

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
        size = len(self.tx.serialize()) * 4
        size += len(self.inputs) * self.extra_input_weight
        return ceil(size / 4)

    @property
    def sigs_count(self):
        # not quite true
        return max([len(inp.partial_sigs) for inp in self.inputs])

    @property
    def addresses(self):
        return [
            out.script_pubkey.address(self.network)
            for out in self.outputs
            if not self.descriptor.owns(out)
        ]

    @property
    def amounts(self):
        return [
            round(out.value * 1e-8, 8)
            for out in self.outputs
            if not self.descriptor.owns(out)
        ]

    @property
    def sats(self):
        return [out.value for out in self.outputs if not self.descriptor.owns(out)]

    @property
    def txid(self):
        return self.tx.txid().hex()

    def to_dict(self):
        return {
            "tx": self.tx.to_dict(self.network),
            "inputs": [inp.to_dict(self.network) for inp in self.inputs],
            "outputs": [out.to_dict(self.network) for out in self.outputs],
            "base64": str(self),
            "fee": round(self.fee() * 1e-8, 8),
            "fee_sat": self.fee(),
            "address": self.addresses,
            "amount": self.amounts,
            "sats": self.sats,
            "tx_full_size": self.full_size,
            "sigs_count": self.sigs_count,
            "time": self.time,
        }
