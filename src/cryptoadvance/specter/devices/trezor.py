from .hwi_device import HWIDevice


class Trezor(HWIDevice):
    device_type = "trezor"
    name = "Trezor"

    def __init__(self, name, alias, keys, fullpath, manager):
        HWIDevice.__init__(self, name, alias, keys, fullpath, manager)
        self.sd_card_support = False
        self.qr_code_support = False
        self.supports_hwi_toggle_passphrase = True
        self.supports_hwi_multisig_display_address = True
