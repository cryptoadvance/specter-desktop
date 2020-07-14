import hashlib
from ..device import Device
from hwilib.serializations import PSBT
from ..helpers import decode_base58, get_xpub_fingerprint, hash160

def _get_xpub_fingerprint(xpub):
    b = decode_base58(xpub)
    return hash160(b[-33:])[:4]

def _der_to_bytes(derivation):
    items = derivation.split("/")
    if len(items) == 0:
        return b''
    if items[0] == 'm':
        items = items[1:]
    if items[-1] == '':
        items = items[:-1]
    res = b''
    for item in items:
        index = 0
        if item[-1] == 'h' or item[-1] == "'":
            index += 0x80000000
            item = item[:-1]
        index += int(item)
        res += index.to_bytes(4,'little')
    return res

class HWIDevice(Device):
    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        Device.__init__(self, name, alias, device_type, keys, fullpath, manager)
        self.hwi_support = True
        self.exportable_to_wallet = False

    def create_psbts(self, base64_psbt, wallet):
        hwi_psbt = PSBT()
        # first fill non_witness_utxo for all inputs
        # and parse
        hwi_psbt.deserialize(wallet.fill_psbt(base64_psbt))
        # for multisig add xpub fields
        if len(wallet.keys) > 1:
            for k in wallet.keys:
                key = b'\x01' + decode_base58(k.xpub)
                if k.fingerprint != '':
                    fingerprint = bytes.fromhex(k.fingerprint)
                else:
                    fingerprint = _get_xpub_fingerprint(k.xpub)
                if k.derivation != '':
                    der = _der_to_bytes(k.derivation)
                else:
                    der = b''
                value = fingerprint + der
                hwi_psbt.unknown[key] = value
        return { 'hwi': hwi_psbt.serialize() }
