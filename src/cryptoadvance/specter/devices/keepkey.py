from . import DeviceTypes
from .hwi_device import HWIDevice
from .hwi.keepkey import KeepkeyClient


class Keepkey(HWIDevice):
    device_type = DeviceTypes.KEEPKEY
    name = "KeepKey"
    icon = "keepkey_icon.svg"

    supports_hwi_toggle_passphrase = True
    supports_hwi_multisig_display_address = True

    @classmethod
    def get_client(cls, *args, **kwargs):
        return KeepkeyClient(*args, **kwargs)
