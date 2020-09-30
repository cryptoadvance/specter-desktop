from .hwi_device import HWIDevice

# a hack that verifies multisig
from .hwi import keepkey


class Keepkey(HWIDevice):
    device_type = "keepkey"
    name = "KeepKey"

    supports_hwi_toggle_passphrase = True
    supports_hwi_multisig_display_address = True

    def __init__(self, name, alias, keys, fullpath, manager):
        HWIDevice.__init__(self, name, alias, keys, fullpath, manager)

    @classmethod
    def get_client(cls, *args, **kwargs):
        return keepkey.KeepkeyClient(*args, **kwargs)
