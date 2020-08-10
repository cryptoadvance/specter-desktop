import hashlib
# from ..device import Device
from .sd_card_device import SDCardDevice
from hwilib.serializations import PSBT
from binascii import a2b_base64
from .. import bcur
from .electrum import b43_encode


class Cobo(SDCardDevice):
    device_type = "cobo"
    name = "Cobo Vault"

    hwi_support = False
    sd_card_support = True
    qr_code_support = True
    exportable_to_wallet = True
    wallet_export_type = 'qr'

    def __init__(self, name, alias, keys, fullpath, manager):
        super().__init__(name, alias, keys, fullpath, manager)

    def create_psbts(self, base64_psbt, wallet):
        psbts = super().create_psbts(base64_psbt, wallet)
        raw_psbt = a2b_base64(base64_psbt)
        enc, hsh = bcur.bcur_encode(raw_psbt)
        qrpsbt = ("ur:bytes/%s/%s" % (hsh, enc)).upper()
        psbts['qrcode'] = qrpsbt
        return psbts

    def export_wallet(self, wallet):
        # Cobo uses ColdCard's style
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
                derivation = k.derivation.replace("h", "'")
                break
        if derivation is None:
            return None
        cc_file = """# CoboVault Multisig setup file (created on Specter Desktop)
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
        enc, hsh = bcur.bcur_encode(cc_file.encode())
        cobo_qr = ("ur:bytes/%s/%s" % (hsh, enc)).upper()
        return cobo_qr
