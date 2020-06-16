from .hwi_device import HWIDevice
from ..serializations import PSBT
from ..helpers import decode_base58, get_xpub_fingerprint, hash160


CC_TYPES = {
    'legacy': 'BIP45',
    'p2sh-segwit': 'P2WSH-P2SH',
    'bech32': 'P2WSH'
}
class ColdCard(HWIDevice):
    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        HWIDevice.__init__(self, name, alias, 'coldcard', keys, fullpath, manager)
        self.sd_card_support = True
        self.qr_code_support = False

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

    def get_wallet_file(self, wallet):
        CC_TYPES = {
        'legacy': 'BIP45',
        'p2sh-segwit': 'P2WSH-P2SH',
        'bech32': 'P2WSH'
        }
        # try to find at least one derivation
        # cc assume the same derivation for all keys :(
        derivation = None
        for k in wallet.keys:
            if k.derivation != '':
                derivation = k.derivation.replace("h","'")
                break
        if derivation is None:
            return None
        cc_file = """# Coldcard Multisig setup file (created on Specter Desktop)
#
Name: {}
Policy: {} of {}
Derivation: {}
Format: {}
""".format(wallet.name, wallet.sigs_required, 
            len(wallet.keys), derivation,
            CC_TYPES[wallet.address_type]
            )
        for k in wallet.keys:
            # cc assumes fingerprint is known
            fingerprint = k.fingerprint
            if fingerprint == '':
                fingerprint = get_xpub_fingerprint(k.xpub).hex()
            cc_file += "{}: {}\n".format(fingerprint.upper(), k.xpub)
        return cc_file

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
