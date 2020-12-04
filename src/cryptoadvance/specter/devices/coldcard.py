import urllib
from .sd_card_device import SDCardDevice
from ..util.xpub import get_xpub_fingerprint
from ..helpers import to_ascii20
from embit.psbt import PSBT, DerivationPath
from embit import bip32
from binascii import b2a_base64, a2b_base64
from collections import OrderedDict

CC_TYPES = {"legacy": "BIP45", "p2sh-segwit": "P2WSH-P2SH", "bech32": "P2WSH"}


class ColdCard(SDCardDevice):
    device_type = "coldcard"
    name = "ColdCard"
    icon = "coldcard_icon.svg"

    sd_card_support = True
    wallet_export_type = "file"
    supports_hwi_multisig_display_address = True

    def __init__(self, name, alias, keys, fullpath, manager):
        SDCardDevice.__init__(self, name, alias, keys, fullpath, manager)

    def replace_derivations(self, wallet, psbts):
        # cc wants everyone to use the same derivation
        fgp = None
        derivation = None
        for k in wallet.keys:
            if k in self.keys and k.fingerprint and k.derivation:
                fgp = k.fingerprint
                derivation = k.derivation
                break
        if not fgp:
            return
        path = bip32.parse_path(derivation)
        for kk in list(psbts.keys()):
            psbt = PSBT.parse(a2b_base64(psbts[kk]))
            for xpub in psbt.xpubs:
                psbt.xpubs[xpub].derivation = list(path)
            # remove partial signatures from device psbt
            for scope in psbt.inputs:
                scope.partial_sigs = OrderedDict()
            for scope in psbt.inputs + psbt.outputs:
                for k in list(scope.bip32_derivations.keys()):
                    original = scope.bip32_derivations[k].derivation
                    scope.bip32_derivations[k].derivation = path + original[-2:]
            psbts[kk] = b2a_base64(psbt.serialize()).decode().strip()

    def create_psbts(self, base64_psbt, wallet):
        psbts = SDCardDevice.create_psbts(self, base64_psbt, wallet)
        psbts["sdcard"] = wallet.fill_psbt(
            psbts["sdcard"], non_witness=False, xpubs=True
        )
        self.replace_derivations(wallet, psbts)
        return psbts

    def export_wallet(self, wallet):
        if not wallet.is_multisig:
            return None
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
