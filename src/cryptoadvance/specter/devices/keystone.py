from . import DeviceTypes
from .cobo import Cobo
from ..helpers import to_ascii20
from ..util.xpub import get_xpub_fingerprint
from binascii import b2a_base64


class Keystone(Cobo):
    device_type = DeviceTypes.KEYSTONE
    name = "Keystone"
    icon = "keystone_icon.svg"

    def create_psbts(self, base64_psbt, wallet):
        psbts = super().create_psbts(base64_psbt, wallet)
        # make sure nonwitness and xpubs are not there
        qr_psbt = wallet.fill_psbt(base64_psbt, non_witness=False, xpubs=False)
        # add a hint to <qr-code> tag that this should be encoded as crypto-psbt
        psbts["qrcode"] = f"crypto-psbt:{qr_psbt}"
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
        walletdata = b2a_base64(cc_file.encode()).decode()
        return f"ur-bytes:{walletdata}"
