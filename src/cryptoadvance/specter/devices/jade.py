from . import DeviceTypes
from .hwi_device import HWIDevice
from .hwi.jade import JadeClient
from .hwi.jade import enumerate as jade_enumerate
from ..helpers import is_liquid


class Jade(HWIDevice):
    device_type = DeviceTypes.JADE
    name = "Jade"
    icon = "jade_icon.svg"

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
