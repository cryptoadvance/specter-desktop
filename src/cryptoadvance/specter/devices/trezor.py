from .hwi_device import HWIDevice
from hwilib.devices.trezor import TrezorClient


class Trezor(HWIDevice):
    device_type = "trezor"
    name = "Trezor"
    icon = "img/devices/trezor_icon.svg"

    supports_hwi_toggle_passphrase = True
    supports_hwi_multisig_display_address = True

    @classmethod
    def get_client(cls, *args, **kwargs):
        return TrezorClient(*args, **kwargs)
