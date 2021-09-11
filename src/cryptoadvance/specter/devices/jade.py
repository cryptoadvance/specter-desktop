from . import DeviceTypes
from .hwi_device import HWIDevice
from .hwi.jade import JadeClient
from .hwi.jade import enumerate as jade_enumerate


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
        return jade_enumerate(*args, **kwargs)
