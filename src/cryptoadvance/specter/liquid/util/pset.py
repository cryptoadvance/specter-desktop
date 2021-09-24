from embit.liquid.pset import PSET, LInputScope, LOutputScope
from embit.liquid.transaction import LTransaction, LTransactionOutput
from embit.liquid.networks import get_network
from embit.liquid.addresses import address as liquid_address
from embit import bip32, ec
from math import ceil
import time
from cryptoadvance.specter.util.psbt import *


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


class SpecterLTx(SpecterTx):
    def vout_to_dict(self, vout):
        i = self.tx.vout.index(vout)
        return {
            "value": round(1e-8 * vout.value, 8),
            "sats": vout.value,
            "n": i,
            "asset": vout.asset[::-1].hex(),
            "scriptPubKey": {
                "hex": vout.script_pubkey.data.hex(),
                "addresses": [get_address(vout.script_pubkey, self.network)],
            },
        }


class SpecterLInputScope(SpecterInputScope):
    TxCls = SpecterLTx

    @property
    def assetid(self):
        return self.scope.asset[::-1].hex()

    @property
    def address(self):
        # TODO: blinding key?
        return liquid_address(self.scope.script_pubkey, network=self.network)

    @property
    def sat_amount(self):
        return self.scope.value

    def to_dict(self):
        obj = super().to_dict()
        obj.update({"asset": self.assetid})
        return obj


class SpecterLOutputScope(SpecterOutputScope):
    @property
    def assetid(self):
        return self.scope.asset[::-1].hex()

    @property
    def address(self):
        if not self.scope.script_pubkey.data:
            return "Fee"
        return liquid_address(
            self.scope.script_pubkey, self.blinding_key, network=self.network
        )

    @property
    def blinding_key(self):
        if self.scope.blinding_pubkey:
            return ec.PublicKey.parse(self.scope.blinding_pubkey)

    @property
    def sat_amount(self):
        return self.scope.value

    def to_dict(self):
        obj = super().to_dict()
        obj.update({"asset": self.assetid})
        return obj


class SpecterPSET(SpecterPSBT):
    """Specter's PSBT class with some handy functions"""

    PSBTCls = PSET
    InputCls = SpecterLInputScope
    OutputCls = SpecterLOutputScope
    TxCls = SpecterLTx

    @property
    def addresses(self):
        return [
            out.address
            for out in self.outputs
            if out.scope.script_pubkey.data and not self.descriptor.owns(out.scope)
        ]

    @property
    def assets(self):
        return [
            out.assetid
            for out in self.outputs
            if out.scope.script_pubkey.data and not self.descriptor.owns(out.scope)
        ]

    def to_dict(self):
        obj = super().to_dict()
        obj.update({"asset": self.assets})
        return obj
