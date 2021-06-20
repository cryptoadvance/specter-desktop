from . import DeviceTypes
from .hwi_device import HWIDevice
from .hwi.jade import JadeClient, enumerate


class Jade(HWIDevice):
    device_type = DeviceTypes.JADE
    name = "Jade"
    icon = "jade_icon.svg"

    supports_hwi_toggle_passphrase = False
    supports_hwi_multisig_display_address = False

    @classmethod
    def get_client(cls, *args, **kwargs):
        return JadeClient(*args, **kwargs)

    @classmethod
    def enumerate(cls, *args, **kwargs):
        return enumerate(*args, **kwargs)

    def has_key_types(self, wallet_type, network="main"):
        if wallet_type == "multisig":
            return False
        return super().has_key_types(wallet_type, network)

    def no_key_found_reason(self, wallet_type, network="main"):
        if wallet_type == "multisig":
            return "Jade does not yet support multisig wallets."
        return super().no_key_found_reason(wallet_type, network)
