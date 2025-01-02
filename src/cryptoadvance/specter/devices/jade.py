from .hwi_device import HWIDevice
from .hwi.jade import JadeClient
from .hwi.jade import enumerate as jade_enumerate
from ..helpers import is_liquid, to_ascii20
from ..util import bcur
from binascii import b2a_base64


class Jade(HWIDevice):
    device_type = "jade"
    name = "Jade"
    icon = "img/devices/jade_icon.svg"

    qr_code_support = True
    supported_qr_code_format = "crypto-psbt"
    qr_code_support_verify = True
    sd_card_support = False
    supports_qr_message_signing = True
    supports_hwi_toggle_passphrase = False
    supports_hwi_multisig_display_address = True
    supports_multisig_registration = True
    liquid_support = True
    exportable_to_wallet = True
    wallet_export_type = "qr"

    @classmethod
    def get_client(cls, *args, **kwargs):
        return JadeClient(*args, **kwargs)

    @classmethod
    def enumerate(cls, *args, **kwargs):
        return jade_enumerate(*args, **kwargs)

    def has_key_types(self, wallet_type, network="main"):
        if wallet_type == "multisig" and is_liquid(network):
            return False
        return super().has_key_types(wallet_type, network)

    def no_key_found_reason(self, wallet_type, network="main"):
        if wallet_type == "multisig" and is_liquid(network):
            return "Jade does not support multisig wallets on Liquid."
        return super().no_key_found_reason(wallet_type, network)

    # For signing PSBTs via QR code on the Jade
    def create_psbts(self, base64_psbt, wallet):
        psbts = super().create_psbts(base64_psbt, wallet)
        qr_psbt = wallet.fill_psbt(base64_psbt, non_witness=False, xpubs=False)
        psbts["qrcode"] = f"{self.supported_qr_code_format}:{qr_psbt}"
        return psbts

    # Enables the export of a multisig wallet to a Jade via QR
    def export_wallet(self, wallet):
        if not wallet.is_multisig:
            return None
        # Jade uses ColdCard's style (assumes derivation paths of the keys to be the same)
        CC_TYPES = {"legacy": "BIP45", "p2sh-segwit": "P2WSH-P2SH", "bech32": "P2WSH"}
        derivation = None
        for k in wallet.keys:
            if k in self.keys and k.derivation != "":
                derivation = k.derivation.replace("h", "'")
                break
        if derivation is None:
            return None
        qr_string = """
        Name: {}
        Policy: {} of {}
        Derivation: {}
        Format: {}
        Sorted: {}
        """.format(
            to_ascii20(wallet.name),
            wallet.sigs_required,
            len(wallet.keys),
            derivation,
            CC_TYPES[wallet.address_type],
            not wallet.uses_multi,
        )

        for k in wallet.keys:
            fingerprint = k.fingerprint
            if fingerprint == "":
                fingerprint = get_xpub_fingerprint(k.xpub).hex()
            qr_string += "{}: {}\n".format(
                fingerprint.upper(),
                k.xpub,
            )

        qr_string = b2a_base64(qr_string.encode()).decode()
        return f"ur-bytes:{qr_string}"

        # Example output:
        # """
        # Name: MyWallet
        # Policy: 2 of 3
        # Derivation: m/48'/1'/0'/2'
        # Format: P2WSH
        # Sorted: False
        # A1B2C3D4: tpubD6NzVbkrYhZ...
        # F2E3D4C5: tpubE6NzVhkxF7Q...
        # """
