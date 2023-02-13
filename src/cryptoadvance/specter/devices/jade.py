from .hwi_device import HWIDevice
from .hwi.jade import JadeClient
from .hwi.jade import enumerate as jade_enumerate
from ..helpers import is_liquid


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
