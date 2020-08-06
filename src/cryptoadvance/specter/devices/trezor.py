from .hwi_device import HWIDevice


class Trezor(HWIDevice):
    device_type = "trezor"
    name = "Trezor"

    supports_hwi_toggle_passphrase = True
    supports_hwi_multisig_display_address = True

    def __init__(self, name, alias, keys, fullpath, manager):
        HWIDevice.__init__(self, name, alias, keys, fullpath, manager)
