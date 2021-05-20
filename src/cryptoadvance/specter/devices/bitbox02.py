from .hwi_device import HWIDevice


class BitBox02(HWIDevice):
    device_type = "bitbox02"
    name = "BitBox02"
    icon = "bitbox02_icon.svg"
    supports_hwi_multisig_display_address = True

    def __init__(self, name, alias, keys, blinding_key, fullpath, manager):
        HWIDevice.__init__(self, name, alias, keys, blinding_key, fullpath, manager)
