from .hwi_device import HWIDevice
from ..helpers import decode_base58, get_xpub_fingerprint, hash160
from hwilib.serializations import PSBT


class SDCardDevice(HWIDevice):
    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        HWIDevice.__init__(self, name, alias, device_type, keys, fullpath, manager)
        self.sd_card_support = True
        self.exportable_to_wallet = True

    def create_psbts(self, base64_psbt, wallet):
        psbts = HWIDevice.create_psbts(self, base64_psbt, wallet)
        sdcard_psbt = PSBT()
        sdcard_psbt.deserialize(base64_psbt)
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
                sdcard_psbt.unknown[key] = value
        psbts['sdcard'] = sdcard_psbt.serialize()
        return psbts

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
        res += index.to_bytes(4,'big')
    return res
