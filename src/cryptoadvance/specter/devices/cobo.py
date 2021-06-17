import hashlib

# from ..device import Device
from . import DeviceTypes
from .coldcard import ColdCard
from hwilib.psbt import PSBT
from binascii import a2b_base64
from ..util import bcur
from ..util.xpub import get_xpub_fingerprint
from ..helpers import to_ascii20


class Cobo(ColdCard):
    device_type = DeviceTypes.COBO
    name = "Cobo Vault"
    icon = "cobo_icon.svg"

    hwi_support = False
    sd_card_support = True
    qr_code_support = True
    exportable_to_wallet = True
    wallet_export_type = "qr"

    def create_psbts(self, base64_psbt, wallet):
        psbts = super().create_psbts(base64_psbt, wallet)
        # make sure nonwitness and xpubs are not there
        psbts["qrcode"] = wallet.fill_psbt(base64_psbt, non_witness=False, xpubs=False)
        raw_psbt = a2b_base64(psbts["qrcode"])
        enc, hsh = bcur.bcur_encode(raw_psbt)
        qrpsbt = ("ur:bytes/%s/%s" % (hsh, enc)).upper()
        psbts["qrcode"] = qrpsbt
        return psbts

    def export_wallet(self, wallet):
        if not wallet.is_multisig:
            return None
        # Cobo uses ColdCard's style
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
        cc_file = """
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
        enc, hsh = bcur.bcur_encode(cc_file.encode())
        cobo_qr = ("ur:bytes/%s/%s" % (hsh, enc)).upper()
        return cobo_qr
