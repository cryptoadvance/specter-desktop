from .hwi_device import HWIDevice


class Keepkey(HWIDevice):
    device_type = "keepkey"
    name = "KeepKey"
    icon = "keepkey_icon.svg"

    supports_hwi_toggle_passphrase = True
    supports_hwi_multisig_display_address = True

    def __init__(self, name, alias, keys, fullpath, manager):
        HWIDevice.__init__(self, name, alias, keys, fullpath, manager)
