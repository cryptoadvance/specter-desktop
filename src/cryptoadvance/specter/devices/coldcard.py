import urllib
from .sd_card_device import SDCardDevice
from ..helpers import get_xpub_fingerprint


CC_TYPES = {
    'legacy': 'BIP45',
    'p2sh-segwit': 'P2WSH-P2SH',
    'bech32': 'P2WSH'
}
class ColdCard(SDCardDevice):
    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        SDCardDevice.__init__(self, name, alias, 'coldcard', keys, fullpath, manager)
        self.sd_card_support = True
        self.qr_code_support = False
        self.wallet_export_type = 'file'
        self.supports_hwi_multisig_display_address = True

    def create_psbts(self, base64_psbt, wallet):
        psbts = SDCardDevice.create_psbts(self, base64_psbt, wallet)
        return psbts

    def export_wallet(self, wallet):
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
        return urllib.parse.quote(cc_file)
