from .hwi_device import HWIDevice


class Keepkey(HWIDevice):
    device_type = "keepkey"
    name = "KeepKey"

    def __init__(self, name, alias, keys, fullpath, manager):
        HWIDevice.__init__(self, name, alias, keys, fullpath, manager)
        self.sd_card_support = False
        self.qr_code_support = False
        self.supports_hwi_toggle_passphrase = True
        self.supports_hwi_multisig_display_address = True
