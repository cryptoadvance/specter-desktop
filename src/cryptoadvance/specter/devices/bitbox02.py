from . import DeviceTypes
from .hwi_device import HWIDevice


class BitBox02(HWIDevice):
    device_type = DeviceTypes.BITBOX02
    name = "BitBox02"
    icon = "bitbox02_icon.svg"
    supports_hwi_multisig_display_address = True
