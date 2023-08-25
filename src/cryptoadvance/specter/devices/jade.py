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

    def export_wallet(self, wallet):
        test_string = """
        Name: Jade Multi
        Policy: 2 of 3
        Derivation: m/48'/0'/0'/2'
        Format: P2WSH
        B237FE9D: xpub6E8C7BX4c7qfTsX7urnXggcAyFuhDmYLQhwRwZGLD9maUGWPinuc9k96ejhEQ1DCkSwbwymPxkFt5V1uRug3FweQmZomjkNAiokDaS7xkt5
        249192D2: xpub6EbXynW6xjYR3crcztum6KzSWqDJoAJQoovwamwVnLaCSHA6syXKPnJo6U3bVeGdeEaXAeHsQTxhkLam9Dw2YfoAabtNm44XUWnnUZfHJRq
        67F90FFC: xpub6EHuWWrYd8bp5FS1XAZsMPkmCqLSjpULmygWqAqWRCCjSWQwz6ntq5KnuQnL23No2Jo8qdp48PrL8SVyf14uBrynurgPxonvnX6R5pbit3w
        """
        jade_qr = b2a_base64(test_string.encode()).decode()
        return f"ur-bytes:{jade_qr}"
        return jade_qr
