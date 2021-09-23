from embit.liquid.pset import PSET, LInputScope, LOutputScope
from embit.liquid.transaction import LTransaction, LTransactionOutput
from embit.liquid.networks import get_network
from embit.liquid.addresses import address as liquid_address
from embit import bip32, ec
from math import ceil
import time


def to_canonical_pset(pset):
    """
    Removes unblinded information from the transaction
    so Elements Core can decode it
    """
    # if we got psbt, not pset - just return
    if not pset.startswith("cHNl"):
        return pset
    tx = PSET.from_string(pset)

    for inp in tx.inputs:
        inp.value = None
        inp.asset = None
        inp.value_blinding_factor = None
        inp.asset_blinding_factor = None

    for out in tx.outputs:
        if out.is_blinded:
            out.asset = None
            out.asset_blinding_factor = None
            out.value = None
            out.value_blinding_factor = None
    return str(tx)


def get_address(script_pubkey, network):
    return script_pubkey.address(network) if script_pubkey.data else "Fee"


class SpecterLTx(LTransaction):
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
                    "asset": vout.asset.hex(),
                    "scriptPubKey": {
                        "hex": vout.script_pubkey.data.hex(),
                        "addresses": [get_address(vout.script_pubkey, network)],
                    },
                }
                for i, vout in enumerate(self.vout)
            ],
        }


class SpecterLTxOut(LTransactionOutput):
    def to_dict(self, network):
        return {
            "amount": round(self.value * 1e-8, 8),
            "sats": self.value,
            "scriptPubKey": {
                "hex": self.script_pubkey.data.hex(),
                "addresses": [get_address(self.script_pubkey, network)],
            },
        }


class SpecterLInputScope(LInputScope):
    TX_CLS = SpecterLTx
    TXOUT_CLS = SpecterLTxOut

    def __init__(self, *args, **kwargs):
        self.parent = None
        super().__init__(*args, **kwargs)

    @property
    def network(self):
        if self.parent:
            return self.parent.network
        return get_network("liquidv1")

    @property
    def address(self):
        # TODO: blinding key?
        return liquid_address(self.script_pubkey, network=self.network)

    @property
    def float_amount(self):
        return round(self.value * 1e-8, 8)

    def witness_utxo_dict(self, network):
        return {
            "amount": round(self.value * 1e-8, 8),
            "sats": self.value,
            "asset": self.asset.hex(),
            "scriptPubKey": {
                "hex": self.script_pubkey.data.hex(),
                "addresses": [self.address],
            },
        }

    def to_dict(self, network=None):
        network = network or self.network
        obj = {
            "address": self.address,
            "float_amount": self.float_amount,
            "asset": self.asset,
            "sat_amount": self.value,
        }
        obj["witness_utxo"] = self.witness_utxo_dict(network)
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


class SpecterLOutputScope(LOutputScope):
    def __init__(self, *args, **kwargs):
        self.parent = None
        super().__init__(*args, **kwargs)

    @property
    def network(self):
        if self.parent:
            return self.parent.network
        return get_network("liquidv1")

    @property
    def address(self):
        if not self.script_pubkey.data:
            return "Fee"
        return liquid_address(
            self.script_pubkey, self.blinding_eckey, network=self.network
        )

    @property
    def blinding_eckey(self):
        if self.blinding_pubkey:
            return ec.PublicKey.parse(self.blinding_pubkey)

    @property
    def float_amount(self):
        return round(self.value * 1e-8, 8)

    def to_dict(self, network):
        network = network or self.network
        obj = {
            "address": self.address,
            "float_amount": self.float_amount,
            "asset": self.asset,
            "sat_amount": self.value,
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


class SpecterPSET(PSET):
    """Specter's PSBT class with some handy functions"""

    PSBTIN_CLS = SpecterLInputScope
    PSBTOUT_CLS = SpecterLOutputScope
    TX_CLS = SpecterLTx

    def __init__(self, *args, **kwargs):
        self.descriptor = None
        self.network = get_network("liquidv1")
        if "descriptor" in kwargs:
            self.descriptor = kwargs.pop("descriptor")
        if "network" in kwargs:
            self.network = kwargs.pop("network")
        super().__init__(*args, **kwargs)
        # set parent to self so we know about descriptor and network
        for sc in self.inputs + self.outputs:
            sc.parent = self

    def utxo_dict(self):
        return [{"txid": inp.txid.hex(), "vout": inp.vout} for inp in self.inputs]

    @classmethod
    def from_dict(cls, obj, descriptor, chain):
        psbt = cls.from_string(obj["base64"])
        psbt.descriptor = descriptor
        psbt.network = get_network(chain)
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
            out.address
            for out in self.outputs
            if (not self.descriptor.owns(out)) and out.script_pubkey.data
        ]

    @property
    def amounts(self):
        return [
            round(out.value * 1e-8, 8)
            for out in self.outputs
            if (not self.descriptor.owns(out)) and out.script_pubkey.data
        ]

    @property
    def sats(self):
        return [out.value for out in self.outputs if not self.descriptor.owns(out)]

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
            "time": round(time.time(), 6),  # TODO: remove
        }
