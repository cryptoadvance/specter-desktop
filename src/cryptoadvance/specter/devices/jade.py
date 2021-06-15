from .hwi_device import HWIDevice
from .hwi.jade import JadeClient, enumerate


class Jade(HWIDevice):
    device_type = "jade"
    name = "Jade"
    icon = "jade_icon.svg"

    supports_hwi_toggle_passphrase = True
    supports_hwi_multisig_display_address = True

    def __init__(self, name, alias, keys, blinding_key, fullpath, manager):
        HWIDevice.__init__(self, name, alias, keys, blinding_key, fullpath, manager)

    @classmethod
    def get_client(cls, *args, **kwargs):
        return JadeClient(*args, **kwargs)

    @classmethod
    def enumerate(cls, *args, **kwargs):
        return enumerate(*args, **kwargs)
