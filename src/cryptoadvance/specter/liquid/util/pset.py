from embit.liquid.pset import PSET, LInputScope, LOutputScope
from embit.liquid.transaction import LTransaction, LTransactionOutput
from embit.liquid.networks import get_network
from embit.liquid.addresses import address as liquid_address
from embit.liquid import slip77
from embit import bip32, ec, script
from math import ceil
import time
from cryptoadvance.specter.util.psbt import *


def to_canonical_pset(pset: str) -> str:
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


def get_address(script_pubkey: script.Script, network: dict) -> str:
    if not script_pubkey.data:
        return "Fee"
    if script_pubkey.data.startswith(b"\x6a"):
        if len(script_pubkey.data) == 1:
            return "DUMMY"  # dummy output to blind
        else:
            return "OP_RETURN " + script_pubkey.data[1:].hex()
    try:
        return script_pubkey.address(network)
    except:
        return script_pubkey.data.hex()


def get_value(value) -> int:
    if isinstance(value, int):
        return value
    return 0  # confidential


def get_asset(asset) -> bytes:
    if len(asset) != 32:
        return (b"\xFF" * 32).hex()  # confidential
    return asset[::-1].hex()


class SpecterLTx(SpecterTx):
    TxCls = LTransaction

    def vout_to_dict(self, vout: LTransactionOutput) -> dict:
        i = self.tx.vout.index(vout)
        return {
            "value": round(1e-8 * get_value(vout.value), 8),
            "sats": get_value(vout.value),
            "n": i,
            "asset": get_asset(vout.asset),
            "scriptPubKey": {
                "hex": vout.script_pubkey.data.hex(),
                "addresses": [get_address(vout.script_pubkey, self.network)],
            },
        }


class SpecterLInputScope(SpecterInputScope):
    TxCls = SpecterLTx

    @property
    def assetid(self) -> str:
        if self.scope.asset is None:
            return "???"
        return self.scope.asset[::-1].hex()

    @property
    def address(self) -> str:
        # TODO: blinding key?
        try:
            return liquid_address(self.scope.script_pubkey, network=self.network)
        except:
            return None

    @property
    def sat_amount(self) -> int:
        return self.scope.value or 0

    def to_dict(self) -> dict:
        obj = super().to_dict()
        obj.update({"asset": self.assetid})
        return obj


class SpecterLOutputScope(SpecterOutputScope):
    @property
    def assetid(self) -> str:
        if self.scope.asset is None:
            return "???"
        return self.scope.asset[::-1].hex()

    @property
    def address(self) -> str:
        if not self.scope.script_pubkey.data:
            return "Fee"
        if self.scope.script_pubkey.data.startswith(b"\x6a"):
            if len(self.scope.script_pubkey.data) == 1:
                return "DUMMY"  # dummy output to blind
            else:
                return "OP_RETURN " + self.scope.script_pubkey.data[1:].hex()
        try:
            # try making a liquid address
            return liquid_address(
                self.scope.script_pubkey, self.blinding_key, network=self.network
            )
        except:
            # if failed - return hex of the scriptpubkey
            return self.scope.script_pubkey.data.hex()

    def extra_weight(self) -> int:
        wit = 0
        if self.scope.is_blinded:
            wit += 33 * 4  # nonce
            wit += (33 - 9) * 4  # value
            if self.scope.range_proof and self.scope.surjection_proof:
                # serialized witness length
                wit += (
                    len(self.scope.surjection_proof) + len(self.scope.range_proof) + 3
                )
            else:
                # we don't have proofs yet but we can estimate their size
                wit += 4245
        return wit

    @property
    def blinding_key(self) -> ec.PublicKey:
        if self.scope.blinding_pubkey:
            return ec.PublicKey.parse(self.scope.blinding_pubkey)

    @property
    def sat_amount(self) -> int:
        return self.scope.value or 0

    def to_dict(self) -> dict:
        obj = super().to_dict()
        obj.update({"asset": self.assetid})
        return obj


class SpecterPSET(SpecterPSBT):
    """Specter's PSBT class with some handy functions"""

    PSBTCls = PSET
    InputCls = SpecterLInputScope
    OutputCls = SpecterLOutputScope
    TxCls = SpecterLTx

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.psbt.verify(ignore_missing=True)

    @property
    def full_size(self) -> int:
        size = len(self.psbt.tx.serialize()) * 4
        # witness and redeem script
        size += len(self.inputs) * self.extra_input_weight
        for out in self.outputs:
            size += out.extra_weight()
        return ceil(size / 4)

    def should_display(self, out: SpecterLOutputScope) -> bool:
        """Checks if this output should be displayed"""
        if not out.scope.script_pubkey.data:
            # Fee
            return False
        if out.scope.value == 0 and out.scope.script_pubkey.data == b"\x6a":
            # Dummy output
            return False
        return super().should_display(out)

    @property
    def assets(self) -> List[str]:
        return [out.assetid for out in self.outputs if self.should_display(out)]

    def to_dict(self) -> dict:
        obj = super().to_dict()
        obj.update({"asset": self.assets})
        return obj
