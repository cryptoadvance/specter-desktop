import urllib
from .sd_card_device import SDCardDevice
from ..util.xpub import get_xpub_fingerprint
from ..helpers import to_ascii20

CC_TYPES = {"legacy": "BIP45", "p2sh-segwit": "P2WSH-P2SH", "bech32": "P2WSH"}


class ColdCard(SDCardDevice):
    device_type = "coldcard"
    name = "ColdCard"

    sd_card_support = True
    wallet_export_type = "file"
    supports_hwi_multisig_display_address = True

    def __init__(self, name, alias, keys, fullpath, manager):
        SDCardDevice.__init__(self, name, alias, keys, fullpath, manager)

    def create_psbts(self, base64_psbt, wallet):
        psbts = SDCardDevice.create_psbts(self, base64_psbt, wallet)
        return psbts

    def export_wallet(self, wallet):
        CC_TYPES = {"legacy": "BIP45", "p2sh-segwit": "P2WSH-P2SH", "bech32": "P2WSH"}
        # try to find at least one derivation
        # cc assume the same derivation for all keys :(
        derivation = None
        # find correct key
        for k in wallet.keys:
            if k in self.keys and k.derivation != "":
                derivation = k.derivation.replace("h", "'")
                break
        if derivation is None:
            return None
        cc_file = """# Coldcard Multisig setup file (created on Specter Desktop)
#
Name: {}
Policy: {} of {}
Derivation: {}
Format: {}
""".format(
            to_ascii20(wallet.name),
            wallet.sigs_required,
            len(wallet.keys),
            derivation,
            CC_TYPES[wallet.address_type],
        )
        for k in wallet.keys:
            # cc assumes fingerprint is known
            fingerprint = k.fingerprint
            if fingerprint == "":
                fingerprint = get_xpub_fingerprint(k.xpub).hex()
            cc_file += "{}: {}\n".format(fingerprint.upper(), k.xpub)
        return urllib.parse.quote(cc_file)
